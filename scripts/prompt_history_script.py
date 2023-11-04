from cProfile import label
import math

from sympy import true
from lib_history import global_state, history, hijacker, image_process_hijacker
import importlib
importlib.reload(global_state)
importlib.reload(hijacker)
importlib.reload(history)
importlib.reload(image_process_hijacker)

import modules.images as images
import modules.generation_parameters_copypaste as parameters_copypaste
from PIL import Image
import time
import html
import gradio as gr
import json
import os
from modules import script_callbacks, shared, scripts, ui_components

config_dir = os.path.join(scripts.basedir(), "data")
config_file_path = "data.json"
current_code = ""
origin_code = "'"
active_id = ""
manual_save_history = None
# pagination
total_pages = 1
current_page = 1



def read_config():
    # ensure history exist
    os.makedirs(config_dir, exist_ok=True)
    cfgPath = os.path.join(config_dir, config_file_path)
    # only load config data if exist
    if os.path.exists(cfgPath):
        with open(cfgPath, "r", encoding="utf-8") as f:
            data = json.load(f)
            for hr in data:
                h = history.History(hr["id"], hr["name"], hr["model"], hr["info_text"])
                h.created_at = hr["created_at"]
                global_state.config_histories.append(h)

def to_json():
    if not global_state.config_histories:
        return ""
    data = list()
    for h in global_state.config_histories:
        data.append(h.to_json())
    return json.dumps(data, indent=2)

def save_history():
    cfgPath = os.path.join(config_dir, config_file_path)
    with open(cfgPath, "w", encoding="utf-8") as outfile:
        outfile.write(to_json())

def add_config(id: str, name: str, model: str, info_text: str, img) -> history.History:
    # init new history
    h = history.History(id, name, model, info_text)
    
    # shorten name
    original_prompt = h.name
    h.name = h.name[:64]
    # replace default prompts
    info_texts = info_text.splitlines(True) 
    info_texts[0] = original_prompt + '\n'
    h.info_text = ''.join(info_texts)
    
    # in case of not automatic save, we must store few items in case of manual saved
    if not global_state.automatic_save:
        global manual_save_history
        manual_save_history = {
            "history": h,
            "image": img,
        }
        return
    
    # save image
    imageType = global_state.save_thumbnail
    if imageType == "": imageType = "full"
    if imageType == "thumbnail":
        new_width  = 300
        new_height = int(new_width * img.height / img.width)
        img = img.resize((new_width, new_height), Image.LANCZOS)
        images.save_image(image=img, path=global_state.history_path, basename="", forced_filename=f"{id}", extension="jpg", save_to_dirs=False)
    elif imageType == "full":
        images.save_image(image=img, path=global_state.history_path, basename="", forced_filename=f"{id}", extension="jpg", save_to_dirs=False)
        
    # add history to list
    global_state.config_histories.insert(0, h)
    
    # save to file
    save_history()
    
    # reload the UI
    global_state.config_changed = True
    return h
    
def manually_save():
    global manual_save_history
    if manual_save_history is not None:
        img = manual_save_history["image"]
        h = manual_save_history["history"]
        # save image
        imageType = global_state.save_thumbnail
        if imageType == "": imageType = "full"
        if imageType == "thumbnail":
            new_width  = 300
            new_height = int(new_width * img.height / img.width)
            img = img.resize((new_width, new_height), Image.LANCZOS)
            images.save_image(image=img, path=global_state.history_path, basename="", forced_filename=f"{h.id}", extension="jpg", save_to_dirs=False)
        elif imageType == "full":
            images.save_image(image=img, path=global_state.history_path, basename="", forced_filename=f"{h.id}", extension="jpg", save_to_dirs=False)
            
        # add history to list
        global_state.config_histories.insert(0, h)
        
        # save to file
        save_history()
        
        # reload the UI
        global_state.config_changed = True
        
        # clean 
        manual_save_history = None
    
def before_ui():
    global config_dir
    global_state.is_enabled = shared.opts.data.get('prompt_history_enabled', True)
    global_state.automatic_save = shared.opts.data.get('prompt_history_automatic_save_info', True)
    global_state.save_thumbnail = shared.opts.data.get('prompt_history_save_thumbnail', "full")
    global_state.table_thumb_size = int(shared.opts.data.get('prompt_history_preview_thumb_size_inline', 96))
    global_state.items_per_page = int(shared.opts.data.get('prompt_history_items_per_page', 15))
    setup_data_dir = shared.opts.data.get('prompt_history_data_path', config_dir) 
    if setup_data_dir != "":
        config_dir = setup_data_dir
        global_state.history_path = setup_data_dir
    else:
        global_state.history_path = setup_data_dir
    global_state.add_config = add_config
    read_config()

def on_ui_tabs():
    with gr.Blocks(analytics_enabled=False) as ui:
        with gr.Row():
            save_last_prompt_btn = gr.Button("Save Last Generated Info", elem_id="prompt_history_save_btn", visible=not global_state.automatic_save)
        with gr.Row():
            with gr.Column(scale=7): 
                # list display column
                table = gr.HTML('Loading...')
                ui.load(fn=history_table, inputs=[], outputs=[table, save_last_prompt_btn], every=1)
                # receiver buttons
                item_id_text = gr.Text(elem_id="prompt_history_item_id_text", visible=False)
                click_item_btn = gr.Button(elem_id="prompt_history_click_item_btn", visible=False)
                delete_item_btn = gr.Button(elem_id="prompt_history_delete_item_btn", visible=False)
                prev_btn = gr.Button(elem_id="prompt_history_prev_btn", visible=False)
                next_btn = gr.Button(elem_id="prompt_history_next_btn", visible=False)
            with gr.Column(scale=3): # image preview and details column
                with gr.Row():
                    # image preview
                    preview_image = gr.Image(
                        label="Preview",
                        show_label=True,
                        interactive=False,
                        width=300,
                    )
                with gr.Row():
                    apply_btn = gr.Button("Apply")
                with gr.Row():
                    edit_btn =  gr.Button("🖊️", visible=False, elem_classes=["tool_fixed"])
                    revert_btn =  gr.Button("❌", visible=False, elem_classes=["tool_fixed"])
                    save_btn = gr.Button("💾", visible=False, elem_classes=["tool_fixed"])
                with gr.Row():
                    code_block = gr.Code(
                        label="Code",
                        show_label=True,
                        interactive=False,
                    )
        # manual save last generated info
        save_last_prompt_btn.click(
            fn=manually_save,
        )
        
        # process when click edit button
        edit_btn.click(
            fn=lambda: {
                code_block: gr.update(interactive=True),
                revert_btn: gr.update(visible=True),
                save_btn: gr.update(visible=True),
                edit_btn: gr.update(visible=False),
            },
            outputs=[code_block, revert_btn, save_btn, edit_btn]
        )
        
        def prev_func():
            global current_page
            if global_state.config_changed: return
            global_state.config_changed = True
            current_page -= 1
            if current_page <= 0: current_page = 1
        prev_btn.click(
            fn=prev_func,
        )
        
        def next_func():
            global current_page
            if global_state.config_changed: return
            global_state.config_changed = True
            current_page += 1
            if current_page > total_pages: current_page = total_pages
        next_btn.click(
            fn=next_func,
        )
        
        # revert code func
        def revert_func():
            global current_code
            current_code = origin_code
            return {
                code_block: gr.update(value=origin_code, interactive=False),
                revert_btn: gr.update(visible=False),
                save_btn: gr.update(visible=False),
                edit_btn: gr.update(visible=True),
            }
        revert_btn.click(
            fn=revert_func,
            outputs=[code_block, revert_btn, save_btn, edit_btn]
        )
        
        # save code func
        def code_change_func(text: str):
            global current_code
            current_code = text
        code_block.change(
            fn=code_change_func,
            inputs=[code_block],
            outputs=[]
        )
        def apply_func():
            # edit info code in history object and save to file
            global active_id, current_code
            for h in global_state.config_histories:
                if h.id == active_id:
                    h.info_text = current_code
                    save_history()
                    break
            # update state
            return {
                code_block: gr.update(interactive=False),
                revert_btn: gr.update(visible=False),
                save_btn: gr.update(visible=False),
                edit_btn: gr.update(visible=True),
            }
        save_btn.click(
            fn=apply_func,
            outputs=[code_block, revert_btn, save_btn, edit_btn]
        )
        
        # register paste for apply button
        parameters_copypaste.register_paste_params_button(parameters_copypaste.ParamBinding(
            paste_button=apply_btn, tabname="txt2img", source_text_component=code_block, source_image_component=None,
        ))
        
        # process when click to item
        click_item_btn.click(
            fn=on_click_item,
            inputs=[item_id_text],
            outputs=[preview_image, code_block, edit_btn],
            show_progress=False,
        )
        
        # process when delete button
        delete_item_btn.click(
            fn=on_delete_item,
            inputs=[item_id_text],
            show_progress=False,
        )
        return [(ui, "Prompt History", "extension_prompt_history_tab")]

def on_delete_item(id: str):
    for _id in id.split(','):
        for h in global_state.config_histories:
            if h.id == _id:
                img_path = os.path.join(config_dir, f"{h.id}.jpg")
                if os.path.isfile(img_path):
                    os.remove(img_path)
                global_state.config_histories.remove(h)
    save_history()
    global_state.config_changed = True
    return []

def on_click_item(id: str):
    global current_code, origin_code, active_id
    for h in global_state.config_histories:
        if h.id == id:
            active_id = h.id
            current_code = h.info_text
            origin_code = h.info_text
            img_path = os.path.join(config_dir, f"{h.id}.jpg")
            global_state.config_changed = True
            img = Image.open(img_path) if os.path.isfile(img_path) else None
            return img, h.info_text, gr.update(visible=True)

def config_changed(orginal_cfg:None, new_cfg:None):
    if orginal_cfg != new_cfg:
        global_state.config_changed = True
    return new_cfg
    
def history_table():
    global manual_save_history, total_pages, current_page, config_dir
    # update config variables
    global_state.is_enabled = config_changed(global_state.is_enabled, shared.opts.data.get('prompt_history_enabled', True))
    global_state.automatic_save = config_changed(global_state.automatic_save, shared.opts.data.get('prompt_history_automatic_save_info', True))
    global_state.save_thumbnail = config_changed(global_state.save_thumbnail, shared.opts.data.get('prompt_history_save_thumbnail', "full"))
    global_state.table_thumb_size = config_changed(global_state.table_thumb_size, int(shared.opts.data.get('prompt_history_preview_thumb_size_inline', 96)))
    global_state.items_per_page = config_changed(global_state.items_per_page, int(shared.opts.data.get('prompt_history_items_per_page', 15)))
    setup_data_dir = config_changed(shared.opts.data.get('prompt_history_data_path', config_dir))
    if setup_data_dir != "":
        config_dir = setup_data_dir
        global_state.history_path = setup_data_dir
    else:
        global_state.history_path = setup_data_dir
    
    active_class = "pmt_item_active"
    
    if global_state.config_changed or not global_state.cached_data:
        
        code = f"""
        <div class="g-table-body">
        <button class="lg secondary gradio-button" onclick="return promptHistoryMultiselectDelete()"  style="padding: 0 10px;" id="prompt_history_btn_delete_selected">❌ Delete Selected</button>
        <table cellspacing="0" class="g-table-list" id="prompt-history-table">
            <thead>
                <tr>
                    <th style="cursor: pointer;width: 80px;display: flex;flex-direction: row;">
                        <input type="checkbox"onclick="return promptHistorySelectAll(this)"  style="cursor:pointer;outline:1px solid #dadada;" />
                    </th>
                    <th class="g-table-list-col-title g-table-list-col-sku required ">Name</th>
                    <th class="g-table-list-col-title g-table-list-col-sku required ">Preview</th>
                    <th class="g-table-list-col-title g-table-list-col-listing opt g-table-list-rwd">Created At</th>
                    <th class="g-table-list-col-title g-table-list-col-date required">Actions</th>
                </tr>
            </thead>
            <tbody>
        """
        
        # calculate pagination
        total_items = len(global_state.config_histories)
        total_pages = math.floor(total_items / global_state.items_per_page)
        if total_pages * global_state.items_per_page < total_items:
            total_pages += 1
        if current_page <= 0: current_page = 1
        if current_page > total_pages: current_page = total_pages
        start_idx = (current_page - 1) * global_state.items_per_page
        end_idx = start_idx + global_state.items_per_page
        if end_idx > total_items: end_idx = total_items
        
        # render page
        for h in global_state.config_histories[start_idx:end_idx]:
            item_class = ""
            if h.id == active_id:
                item_class = active_class
            on_click_view_item_fn =  '"' + html.escape(f"""return promptHistoryItemClick('{h.id}')""") + '"'
            on_click_delete_item_fn =  '"' + html.escape(f"""return promptHistoryItemDelete('{h.id}')""") + '"'
            code += f"""<tr class="{item_class}">
                        <td style="cursor: pointer;vertical-align:top;" onclick="return promptHistorySelect(this)">
                            <input type="checkbox" value="{h.id}" style="pointer-events: none;cursor:pointer;outline:1px solid #dadada;" />
                        </td>
                        <td style="cursor: pointer;" onclick={on_click_view_item_fn} style="width: 90%;">{h.name} - {h.model}</td>
                        <td style="cursor: pointer;vertical-align:top;" onclick={on_click_view_item_fn}>
                            <img src="/file={config_dir}{os.sep}{h.id}.jpg" style="max-width:{global_state.table_thumb_size}px;max-height:{global_state.table_thumb_size}px;">
                        </td>
                        <td style="cursor: pointer;" onclick={on_click_view_item_fn}>{time.ctime(h.created_at)}</td>
                        <td style="width: 110px;"><a onclick={on_click_delete_item_fn} class="g-actions-button g-actions-button-pager">🗑️ Delete</a></td>
                    </tr>"""

        on_click_prev_fn =  '"' + html.escape(f"""return promptHistoryPrev()""") + '"'
        on_click_next_fn =  '"' + html.escape(f"""return promptHistoryNext()""") + '"'
        code += f"""
            </tbody>
        </table>
        <div class="g-table-list-pagination">
            <div class="g-table-list-pagination-col">
                <a href="#" class="g-actions-button g-actions-button-pager" onclick={on_click_prev_fn}>◀️ Prev</a>
                <a href="#">{current_page}/{total_pages}</a>
                <a href="#" class="g-actions-button g-actions-button-pager g-table-list-pager" onclick={on_click_next_fn}>Next ▶️</a>
            </div>
        </div>
        """
        global_state.cached_data = code
        global_state.config_changed = False
    return global_state.cached_data, gr.update(visible=(not global_state.automatic_save and manual_save_history is not None))

def on_ui_settings():
    section = ('prompt_history', 'Prompt History')
    shared.opts.add_option('prompt_history_enabled', shared.OptionInfo(True, 'Enabled', section=section))
    shared.opts.add_option('prompt_history_data_path', shared.OptionInfo(os.path.join(scripts.basedir(), "data"), 'Data Storage Path', section=section))
    shared.opts.add_option("prompt_history_preview_thumb_size_inline", shared.OptionInfo(96, "Preview thumbnail size in table", gr.Number, section=section))
    shared.opts.add_option("prompt_history_items_per_page", shared.OptionInfo(15, "Number of history items display per page", gr.Number, section=section))
    shared.opts.add_option('prompt_history_automatic_save_info', shared.OptionInfo(True, 'Automatic Save (If unset, a button will be display in Prompt History screen for save info manually)', section=section))
    shared.opts.add_option('prompt_history_save_thumbnail', shared.OptionInfo(None, "Save Thumbnail", gr.Dropdown, lambda: {"choices": ["none", "thumbnail", "full"]}, section=section))


script_callbacks.on_ui_settings(on_ui_settings)
script_callbacks.on_before_ui(before_ui)
script_callbacks.on_ui_tabs(on_ui_tabs)
