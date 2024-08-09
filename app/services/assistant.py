import json
import requests
import time
from flask import current_app
from config import Config
from mistralai.models.chat_completion import ChatMessage
from mistralai.client import MistralClient

class AssistantService:
    def __init__(self):
        current_app.logger.info(Config.MISTRALAI_KEY)
        self.client = MistralClient(api_key=Config.MISTRALAI_KEY)

        self.assistant_name = 'IT Administrator Assistant'
        self.model_id = 'mistral-medium-latest'  # Adjust model as needed
        self.instruction = 'You are an IT administrator...'
        self.discussion = []
        self.context_value = ""
        self.cont = True
        self.bot_id = ""
        self.user_id = ""
        self.user_data = {}  # Dictionary to store user-specific data

    def run_assistant(self, message):
        current_app.logger.info(f'Running assistant: {message}')
        self.discussion.append(ChatMessage(role="user", content=message))

        ai_response = self.client.chat(
            model=self.model_id,
            messages=self.discussion
        )

        # Add the assistant response to the discussion
        self.discussion.append(ai_response.choices[0].message)

        # Check if there is a tool call in the response
        tool_calls = ai_response.choices[0].message.tool_calls

        if tool_calls:
            current_app.logger.info(f'Tool calls found: {tool_calls}')
            self.generate_tool_outputs(tool_calls)
            current_app.logger.info(f'Discussion after tool call: {self.discussion}')
            ai_response = self.client.chat(
                model=self.model_id,
                messages=self.discussion
            )
            current_app.logger.info(f'Assistant response after tool call: {ai_response.choices[0].message}')
            self.discussion.append(ChatMessage(role="assistant", content=ai_response.choices[0].message.content))

        current_app.logger.info(f'Assistant response: {ai_response.choices[0].message.content}')
        return ai_response.choices[0].message.content

    def generate_tool_outputs(self, tool_calls):
        current_app.logger.info('Generating tool outputs')
        tool_outputs = []

        for tool_call in tool_calls:
            function_name = tool_call.function.name
            arguments = tool_call.function.arguments

            args_dict = json.loads(arguments)

            if hasattr(self, function_name):
                function_to_call = getattr(self, function_name)
                output = function_to_call(**args_dict)
                current_app.logger.info(f'Tool output: {output}')
                self.discussion.append(ChatMessage(role="tool", function_name=function_name, content=output))

        return tool_outputs

    def define_function__list_available_zones(self):
        function = {
            "type": "function",
            "function": {
                "name": "list_available_zones",
                "description": "List the available zones of the house.",
                "parameters": {
                    "type": "object"
                }
            }
        }
        return function

    def define_function__list_device_status_by_zone(self):
        function = {
            "type": "function",
            "function": {
                "name": "list_device_status_by_zone",
                "description": "List the status of devices in a specific zone.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "zone": {"type": "string", "description": "The zone to list the device status for. Can be 'kitchen' or 'outdoor'."}
                    },
                    "required": ["zone"]
                }
            }
        }
        return function

    def define_function__update_zone_device_status(self):
        function = {
            "type": "function",
            "function": {
                "name": "update_zone_status",
                "description": "Update the status of a device in a specific zone.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "zone": {"type": "string", "description": "The zone to update the status for. Can be 'kitchen' or 'outdoor'."},
                        "device": {"type": "string", "description": "The device to update the status for. Can be 'light', 'door', or 'camera'."},
                    },
                    "required": ["zone", "device"]
                }
            }
        }
        return function

    def list_available_zones(self):
        current_app.logger.info(f'list_available_zones')
        available_zones = current_app.domotics_service.list_available_zones()
        if available_zones:
            current_app.logger.info(f'Available zones found with ref: {available_zones}')
            return json.dumps(available_zones)
        else:
            current_app.logger.info('No available zones found')
            return "No available zone found"

    def list_device_status_by_zone(self, zone):
        current_app.logger.info(f'list_device_status_by_zone: {zone}')
        devices = current_app.domotics_service.list_device_status_by_zone(zone)
        if devices:
            current_app.logger.info(f'Devices found')
            return json.dumps(devices)
        current_app.logger.info('No devices found')
        return "No device found"

    def update_zone_status(self, zone, device):
        current_app.logger.info(f'update_zone_status: {zone}, {device}')
        updated_status = current_app.domotics_service.update_zone_status(zone, device)
        if updated_status:
            current_app.logger.info(updated_status)
            return json.dumps(updated_status)
        else:
            current_app.logger.info('Zone or device not found')
            return "Zone or device not found"

    def ask_mistral(self, prompt):
        self.discussion.append(ChatMessage(role="user", content=prompt))
        response = self.client.chat(
            model=self.model_id,
            messages=self.discussion
        )
        response_text = response.choices[0].message.content
        self.discussion.append(ChatMessage(role="assistant", content=response_text))
        return response_text

    def post_to_ste_chats(self, prompt, response):
        url = 'http://www.onezeus.com:3000/chatsdmlpost'
        data = {
            "CHAT_ID": '',
            "CHAT_PROMPT": prompt,
            "CHAT_RESPONSE": response,
            "AI_MODEL": self.model_id,
            "FROM_USER_ID": self.user_id,
            "TO_USER_ID": self.user_id,
            "CONTEXT": self.context_value,
            "CREATION_DATE": time.strftime('%Y-%m-%dT%H:%M:%S'),
            "CREATED_BY": 'ADMIN',
            "LAST_UPDATE_DATE": time.strftime('%Y-%m-%dT%H:%M:%S'),
            "LAST_UPDATED_BY": 'ADMIN',
            "BOT_ID": self.bot_id
        }
        requests.post(url, json=data)

    def get_bot_by_id(self, bot_id):
        try:
            response = requests.get('http://www.onezeus.com:3000/bots')
            bots = response.json()
            bot = next((b for b in bots if b['BOT_ID'] == bot_id), None)
            if bot:
                self.model_name = bot['BOT_NAME']
                context_string = (
                    f"Your name is {bot['BOT_NAME']}, you only respond as {bot['BOT_NAME']}. "
                    f"You don't include confidence percentages in your responses. "
                    f"Your gender is {bot['GENDER']}. Your appearance is {bot['APPEARANCE']}. "
                    f"Your voice is {bot['VOICE']}. Your teaching style is {bot['TEACHING_STYLE']}. "
                    f"Your subject area of expertise is {bot['SUBJECT_AREA_OF_EXPERTISE']}. "
                    f"And some general background information about you, {bot['BOT_NAME']}, is the following: {bot['BACKGROUND_INFORMATION']}"
                )
                self.discussion.append(ChatMessage(role="system", content=context_string))
            else:
                current_app.logger.info(f'No bot found with BOT_ID {bot_id}')
        except Exception as e:
            current_app.logger.error(f'Error fetching bot data: {e}')

    def get_uuid(self):
        try:
            response = requests.get('http://www.onezeus.com:3000/GenerateUUID')
            return response.json().get('UUID')
        except Exception as e:
            current_app.logger.error(f'Error fetching UUID: {e}')
            return None

    def find_context_values(self, user_id, bot_id):
        try:
            response = requests.get('http://www.onezeus.com:3000/chats')
            data = response.json()
            filtered_data = [item for item in data if item['FROM_USER_ID'] == user_id and item['BOT_ID'] == bot_id]
            if not filtered_data:
                current_app.logger.info('No conversations found, creating new thread')
                self.context_value = self.get_uuid()
                current_app.logger.info(f"Newly generated context value: {self.context_value}")
                self.cont = False
            else:
                unique_contexts = list(set(item['CONTEXT'] for item in filtered_data))
                self.cont = True
                current_app.logger.info(f"Contexts found: {unique_contexts}")
                self.context_value = unique_contexts[0] if unique_contexts else None
        except Exception as e:
            current_app.logger.error(f'Error finding context values: {e}')
            self.context_value = None

    def build_chat_history(self, user_id, bot_id):
        try:
            response = requests.get('http://www.onezeus.com:3000/chats')
            data = response.json()
            filtered_data = [item for item in data if item['FROM_USER_ID'] == user_id and item['BOT_ID'] == bot_id]
            return [(item['CHAT_PROMPT'], item['CHAT_RESPONSE']) for item in filtered_data]
        except Exception as e:
            current_app.logger.error(f'Error building chat history: {e}')
            return []

    def store_user_data(self, key, value):
        """ Store user-specific data in the dictionary """
        self.user_data[key] = value

    def get_user_data(self, key):
        """ Retrieve user-specific data from the dictionary """
        return self.user_data.get(key, None)

    def remember_user_info(self, message):
        """ Parse message to store user information like name """
        if "my name is" in message.lower():
            name = message.lower().split("my name is")[-1].strip()
            self.store_user_data("name", name)
            return f"Nice to meet you, {name}!"
        return "I didn't catch your name. Could you please tell me your name?"

    def run_assistant_with_memory(self, message):
        """ Enhanced run_assistant method that uses memory for user info """
        # Check and process user information
        response = self.remember_user_info(message)
        if response:
            return response

        # Regular assistant functionality
        return self.run_assistant(message)
