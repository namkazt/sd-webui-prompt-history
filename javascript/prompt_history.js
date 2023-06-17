
function promptHistoryItemClick(id) {
    var textarea = gradioApp().querySelector('#prompt_history_item_id_text textarea');
    textarea.value = id;
    updateInput(textarea);

    gradioApp().querySelector('#prompt_history_click_item_btn').click();
}

function promptHistoryItemDelete(id) {
    var textarea = gradioApp().querySelector('#prompt_history_item_id_text textarea');
    textarea.value = id;
    updateInput(textarea);

    gradioApp().querySelector('#prompt_history_delete_item_btn').click();
}

function promptHistoryPrev() {
    gradioApp().querySelector('#prompt_history_prev_btn').click();
}

function promptHistoryNext() {
    gradioApp().querySelector('#prompt_history_next_btn').click();
}

function promptHistoryAutoRefresh() {
    const ll = setInterval(() => {
        const generating = gradioApp().querySelector('#tab_extension_prompt_history_tab .generating');
        if (generating !== undefined && generating !== null) {
            generating.remove();
            clearInterval(ll);
            return;
        }
    }, 1000);
}

onUiLoaded(async() => {
    promptHistoryAutoRefresh()
});