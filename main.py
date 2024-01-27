import time

from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage
import PySimpleGUI as sg
import pyperclip, threading, queue

mistral_model = ["mistral-tiny", "mistral-small", "mistral-medium"]

with open('.api_key', 'r') as f:
    api_key = f.read()

client = MistralClient(api_key=api_key)

sg.set_options(font=("Consolas", 15))

is_receiving = False
is_loop_receive = 0
queue = queue.Queue()
history_list = []

layout = [
    [sg.Text('Question'), sg.Combo(mistral_model, size=(15, 1), key="cb_model", default_value=mistral_model[1])],
    [sg.Multiline('', key='user_question', size=(100, 8), expand_x=True, focus=True)],
    [sg.Button('Send', bind_return_key=True, disabled_button_color='#DDDDDD'), sg.Push(), sg.Button('Clear')],
    [sg.Text('Answer', key='mistral_answer_label')],
    [sg.Multiline('', key='Answer', size=(100, 13), disabled=True, expand_x=True)],
    [sg.Text('History')],
    [sg.Listbox(values=[], size=(100, 6), key='HistoryList', enable_events=True, select_mode=sg.LISTBOX_SELECT_MODE_SINGLE, expand_x=True, expand_y=True)],
    [sg.Button('Show'), sg.Button('Copy'), sg.Push(), sg.Button('Delete'), sg.Button('Delete All')]
]


def _get_history():
    messages = []

    if len(history_list) > 0 and history_list[0].startswith('#assistant'):
        raise Exception("History must start with a user question")

    for history_question in history_list:
        if history_question.startswith('#error'):
            continue
        elif history_question.startswith('#user'):
            history_question = history_question[6:]
            messages.append(ChatMessage(role="user", content=history_question))
        elif history_question.startswith('#assistant'):
            history_question = history_question[11:]
            messages.append(ChatMessage(role="assistant", content=history_question))
        else:
            raise ValueError("Invalid question format: " + history_question)

    return messages


def ask_ai(question, model):
    global is_receiving

    try:
        messages = _get_history()
        messages.append(ChatMessage(role="user", content=question))

        print("Question: " + question)
        is_receiving = True
        full_response = ''
        for chunk in client.chat_stream(model=model, messages=messages):
            response = chunk.choices[0].delta.content
            print(response, end='')
            full_response += response
            queue.put(response)

        history_list.append("#user " + question)
        history_list.append("#assistant " + full_response)
    except Exception as e:
        history_list.append(f"#error {e}")
    finally:
        time.sleep(0.5)
        is_receiving = False


def update_response():
    while not queue.empty():
        text = queue.get()
        window['Answer'].update(text, append=True)
    window.refresh()


def show_popup_selected(selected_text):
    if selected_text.startswith('#user'):
        selected_text = selected_text[6:]
        prefix = '#user'
    elif selected_text.startswith('#assistant'):
        selected_text = selected_text[11:]
        prefix = '#assistant'
    else:
        raise ValueError("Invalid question format: " + selected_text)
    sg.popup_scrolled(selected_text, title=prefix, size=(120, 30))


# Create the window
window = sg.Window('Mistral Call', layout, resizable=True)

# Event Loop
while True:
    try:
        event, values = window.read(timeout=100)
        if event == sg.WIN_CLOSED:
            break
        elif event == 'Send':
            window['Send'].update(disabled=True)
            window['Answer'].update('')
            is_receiving = True

            model_size = values["cb_model"]
            window['mistral_answer_label'].update(f"Mistral [{model_size}] @ {time.strftime('%Y-%m-%d %H:%M:%S')}:")

            thread = threading.Thread(target=ask_ai, args=(values['user_question'], model_size))
            thread.start()
        elif event == 'Clear':
            window['user_question'].update('')
            window['Answer'].update('')
        elif event == 'Delete All':
            history_list = []
            window['HistoryList'].update([])
        elif event == 'Delete':
            if values['HistoryList']:
                selected_text = values['HistoryList'][0]
                for i in range(len(history_list)):
                    if history_list[i][:200] == selected_text[:200]:
                        history_list.pop(i)
                        break
            window['HistoryList'].update(history_list)
        elif event == 'Copy':
            if values['HistoryList']:
                selected_text = values['HistoryList'][0]    # Get the first selected item
                pyperclip.copy(selected_text)               # Copy to clipboard
        elif event == 'Show':
            if values['HistoryList']:
                selected_text = values['HistoryList'][0]
                show_popup_selected(selected_text)
            else:
                sg.popup('No item selected')

        if is_receiving:
            while is_receiving:
                update_response()
                time.sleep(.05)
            window['HistoryList'].update(history_list)
            is_loop_receive = 0
            window['Send'].update(disabled=False)
    except Exception as e:
        window['mistral_answer_label'].update(f"ERROR : {e}")
        time.sleep(1)

window.close()
