# Hypothetical base class
import questllama.core.utils.file_utils as U
import os
from questllama.extensions.client_provider import QuestllamaClientProvider
from langchain.schema import HumanMessage, SystemMessage

from voyager.agents.action import ActionAgent

task = ""

if __name__ == "__main__":
    os.environ["OPENAI_API_KEY"] = "sk-..."

    # Prompt
    while True:
        task_type = "action"
        # i.e. Mine 1 wood log
        task = input("\nQuery: ")
        if task == "exit":
            break
        if task.strip() == "":
            continue

        # Prompt
        if task_type == "action":
            agent = ActionAgent()
            template = agent.render_system_message()
        else:
            template = U.debug_load_prompt(f"{task_type}.txt")
        user = U.debug_load_prompt("/debugging/" + task_type + "/user.txt")
        if task_type == "action" and user.find("{task}") != -1:
            user = user.format(task=task)

        chat = QuestllamaClientProvider()
        msg = chat.generate(
            [
                SystemMessage(content=template.content),
                HumanMessage(content=user),
            ],
            task_type,
        )
        print("Answer: ", msg.answer)
