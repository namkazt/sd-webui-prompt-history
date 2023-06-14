from lib_history import hijacker, global_state
from modules import script_callbacks, processing, shared
import modules.images as images
import uuid
import os

process_images_inner_hijacker = hijacker.ModuleHijacker.install_or_get(
    module=processing,
    hijacker_attribute='__process_images_inner_hijacker',
    on_uninstall=script_callbacks.on_script_unloaded,
)

@process_images_inner_hijacker.hijack('process_images')
def process_images(p: processing.StableDiffusionProcessing, original_function):
    # if prompt history is not enable then call original function
    if not global_state.is_enabled:
        return original_function(p)
    
    # mark old state of return_grid
    # we set it to True to make sure it return grid image in case of multi images
    old_state = shared.opts.return_grid
    shared.opts.return_grid = True
    res = original_function(p)
    shared.opts.return_grid = old_state

    # save image preview with h.id name
    img_id = uuid.uuid4().hex
    img = res.images[0]
    images.save_image_with_geninfo(img, None, os.path.join(global_state.history_path, f"{img_id}.jpg"))
    # add result to history
    global_state.add_config(img_id, res.prompt[:64], shared.opts.sd_model_checkpoint, res.infotexts[0])
    return res

