from lib_history.history import History
from typing import List, Callable
import gradio as gr

# config
is_enabled: bool = True
automatic_save: bool = True
save_thumbnail: bool = True
items_per_page: int = 15
table_thumb_size: int = 136

# data
history_path: str = ""
config_histories: List[History] = list()
config_changed: bool = False
cached_data: str = ""
add_config: Callable
