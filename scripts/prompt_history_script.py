from cProfile import label
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
    
    # in case of not automatic save, we must store few items in case of manual saved
    if not global_state.automatic_save:
        global manual_save_history
        manual_save_history = {
            "history": h,
            "image": img,
        }
        return
    
    # save image
    if global_state.save_thumbnail:
        new_width  = 300
        new_height = int(new_width * img.height / img.width)
        img = img.resize((new_width, new_height), Image.LANCZOS)
        images.save_image_with_geninfo(img, None, os.path.join(global_state.history_path, f"{id}.jpg"))
    else:
        images.save_image_with_geninfo(img, None, os.path.join(global_state.history_path, f"{id}.jpg"))
        
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
        if global_state.save_thumbnail:
            new_width  = 300
            new_height = int(new_width * img.height / img.width)
            img = img.resize((new_width, new_height), Image.LANCZOS)
            images.save_image_with_geninfo(img, None, os.path.join(global_state.history_path, f"{h.id}.jpg"))
        else:
            images.save_image_with_geninfo(img, None, os.path.join(global_state.history_path, f"{h.id}.jpg"))
            
        # add history to list
        global_state.config_histories.insert(0, h)
        
        # save to file
        save_history()
        
        # reload the UI
        global_state.config_changed = True
        
        # clean 
        manual_save_history = None
    
def before_ui():
    global_state.is_enabled = shared.opts.data.get('prompt_history_enabled', True)
    global_state.automatic_save = shared.opts.data.get('prompt_history_automatic_save_info', True)
    global_state.save_thumbnail = shared.opts.data.get('prompt_history_save_thumbnail', True)
    global_state.history_path = config_dir
    global_state.add_config = add_config
    read_config()

def on_ui_tabs():
    with gr.Blocks(analytics_enabled=False) as ui:
        with gr.Row():
            save_last_prompt_btn = gr.Button("Save Last Generated Info", visible=not global_state.automatic_save)
        with gr.Row():
            with gr.Column(scale=1): 
                # list display column
                table = gr.HTML('Loading...')
                ui.load(fn=history_table, inputs=[], outputs=[table, save_last_prompt_btn], every=1)
                # receiver buttons
                item_id_text = gr.Text(elem_id="prompt_history_item_id_text", visible=False)
                click_item_btn = gr.Button(elem_id="prompt_history_click_item_btn", visible=False)
                delete_item_btn = gr.Button(elem_id="prompt_history_delete_item_btn", visible=False)
            with gr.Column(scale=1): # image preview and details column
                with gr.Row():
                    # image preview
                    preview_image = gr.Image(
                        label="Preview",
                        show_label=True,
                        interactive=False,
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
            fn=onClickOnItem,
            inputs=[item_id_text],
            outputs=[preview_image, code_block, edit_btn],
            show_progress=False,
        )
        
        # process when delete button
        delete_item_btn.click(
            fn=onDeleteItem,
            inputs=[item_id_text],
            show_progress=False,
        )
        return [(ui, "Prompt History", "extension_prompt_history_tab")]

def onDeleteItem(id: str):
    for h in global_state.config_histories:
        if h.id == id:
            img_path = os.path.join(config_dir, f"{h.id}.jpg")
            if os.path.isfile(img_path):
                os.remove(img_path)
            global_state.config_histories.remove(h)
    save_history()
    global_state.config_changed = True
    return []

def onClickOnItem(id: str):
    global current_code, origin_code, active_id
    for h in global_state.config_histories:
        if h.id == id:
            active_id = h.id
            current_code = h.info_text
            origin_code = h.info_text
            img_path = os.path.join(config_dir, f"{h.id}.jpg")
            if os.path.isfile(img_path):
                img = Image.open(img_path)
                return img, h.info_text, gr.update(visible=True)

def history_table():
    global manual_save_history
    # update config variables
    global_state.is_enabled = shared.opts.data.get('prompt_history_enabled', True)
    global_state.automatic_save = shared.opts.data.get('prompt_history_automatic_save_info', True)
    global_state.save_thumbnail = shared.opts.data.get('prompt_history_save_thumbnail', True)
    
    if global_state.config_changed or not global_state.cached_data:
        code = f"""
        <div class="g-table-body">
        <table cellspacing="0" class="g-table-list">
            <thead>
                <tr>
                    <th class="g-table-list-col-title g-table-list-col-sku required ">Name</th>
                    <th class="g-table-list-col-title g-table-list-col-listing opt g-table-list-rwd">Created At</th>
                    <th class="g-table-list-col-title g-table-list-col-date required">Actions</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for h in global_state.config_histories:
            onclickViewItem =  '"' + html.escape(f"""return promptHistoryItemClick('{h.id}')""") + '"'
            onclickDeleteItem =  '"' + html.escape(f"""return promptHistoryItemDelete('{h.id}')""") + '"'
            code += f"""<tr>
                        <td style="cursor: pointer;" onclick={onclickViewItem} style="width: 90%;">{h.name} - {h.model}</td>
                        <td style="cursor: pointer;" onclick={onclickViewItem}>{time.ctime(h.created_at)}</td>
                        <td style="width: 110px;"><a onclick={onclickDeleteItem} class="g-actions-button g-actions-button-pager">🗑️ Delete</a></td>
                    </tr>"""

        code += """
            </tbody>
        </table>
        <div class="g-table-list-pagination">
            <div class="g-table-list-pagination-col">
                <a href="#" class="g-actions-button g-actions-button-pager"><i class="fa fa-fw fa-caret-left right-4"></i>Prev</a>
                <a href="#" class="g-actions-button g-actions-button-pager g-table-list-pager">Next<i class="fa fa-fw fa-caret-right left-4"></i></a>
            </div>
        </div>
        """
        global_state.cached_data = code
        global_state.config_changed = False
    return global_state.cached_data, gr.update(visible=(not global_state.automatic_save and manual_save_history is not None))

def on_ui_settings():
    section = ('prompt_history', 'Prompt History')
    shared.opts.add_option('prompt_history_enabled', shared.OptionInfo(True, 'Enabled', section=section))
    shared.opts.add_option('prompt_history_automatic_save_info', shared.OptionInfo(True, 'Automatic Save (If unset, a button will be display in Prompt History screen for save info manually)', section=section))
    shared.opts.add_option('prompt_history_save_thumbnail', shared.OptionInfo(True, 'Save Thumbnail (Save thumbnail instead of full image)', section=section))


script_callbacks.on_ui_settings(on_ui_settings)
script_callbacks.on_before_ui(before_ui)
script_callbacks.on_ui_tabs(on_ui_tabs)
