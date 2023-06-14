from cProfile import label
from lib_history import global_state, history, hijacker, image_process_hijacker
import importlib
importlib.reload(global_state)
importlib.reload(hijacker)
importlib.reload(history)
importlib.reload(image_process_hijacker)

import modules.generation_parameters_copypaste as parameters_copypaste
from PIL import Image
import time
import html
import gradio as gr
import json
import os
import modules
from modules import script_callbacks, shared, scripts

config_dir = os.path.join(scripts.basedir(), "data")
config_file_path = "data.json"

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

def add_config(id: str, name: str, model: str, info_text: str) -> history.History:
    # init new history
    h = history.History(id, name, model, info_text)
    # add history to list
    global_state.config_histories.insert(0, h)
    
    # save to file
    save_history()
    
    # reload the UI
    global_state.config_changed = True
    return h
    
def before_ui():
    global_state.is_enabled = shared.opts.data.get('prompt_history_enabled', True)
    global_state.history_path = config_dir
    global_state.add_config = add_config
    read_config()

def on_ui_tabs():
    with gr.Blocks(analytics_enabled=False) as ui:
        with gr.Row():
            with gr.Column(scale=1): 
                # list display column
                table = gr.HTML('Loading...')
                ui.load(fn=history_table, inputs=[], outputs=[table], every=1)
                # receiver buttons
                itemIdText = gr.Text(elem_id="prompt_history_item_id_text", visible=False)
                clickItemBtn = gr.Button(elem_id="prompt_history_click_item_btn", visible=False)
                deleteItemBtn = gr.Button(elem_id="prompt_history_delete_item_btn", visible=False)
            with gr.Column(scale=1): # image preview and details column
                with gr.Row():
                    # image preview
                    previewImage = gr.Image(
                        label="Preview",
                        show_label=True,
                        interactive=False,
                    )
                with gr.Row():
                    applyBtn = gr.Button("Apply")
                with gr.Row():
                    codeBlock = gr.Code(
                        label="Code",
                        show_label=True,
                    )
       
        parameters_copypaste.register_paste_params_button(parameters_copypaste.ParamBinding(
            paste_button=applyBtn, tabname="txt2img", source_text_component=codeBlock, source_image_component=None,
        ))
        clickItemBtn.click(
            fn=onClickOnItem,
            inputs=[itemIdText],
            outputs=[previewImage, codeBlock],
            show_progress=False,
        )
        deleteItemBtn.click(
            fn=onDeleteItem,
            inputs=[itemIdText],
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
    for h in global_state.config_histories:
        if h.id == id:
            img_path = os.path.join(config_dir, f"{h.id}.jpg")
            if os.path.isfile(img_path):
                img = Image.open(img_path)
                return img, h.info_text

def history_table():
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
    return global_state.cached_data

def on_ui_settings():
    section = ('prompt_history', 'Prompt History')
    shared.opts.add_option('prompt_history_enabled', shared.OptionInfo(True, 'Enabled', section=section))


script_callbacks.on_ui_settings(on_ui_settings)
script_callbacks.on_before_ui(before_ui)
script_callbacks.on_ui_tabs(on_ui_tabs)