from google.cloud import dialogflow_v2 as dialogflow


def test_dialogflow_intent():
    # Настройка клиента
    session_client = dialogflow.SessionsClient.from_service_account_json("small-talk-qpp9-01bbaad3cc34.json")
    session = session_client.session_path("small-talk-qpp9", "test-session-id")

    # Пример текста
    text_input = dialogflow.TextInput(text="Привет", language_code="ru")
    query_input = dialogflow.QueryInput(text=text_input)

    # Отправка запроса в Dialogflow
    response = session_client.detect_intent(session=session, query_input=query_input)

    # Ответ от Dialogflow
    print("Ответ от Dialogflow:", response.query_result.fulfillment_text)


test_dialogflow_intent()
