from lib_history.history import History
from typing import List, Callable
import gradio as gr

is_enabled: bool = True
history_path: str = ""
config_histories: List[History] = list()
config_changed: bool = False
cached_data: str = ""
add_config: Callable
