import os
import uuid
import datetime
import logging
import json
from locust import HttpUser, task, between
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

class ApiUser(HttpUser):
    wait_time = between(1, 3)  # Time between consecutive tasks
    host = "https://app-api-ocwiawb26beca.azurewebsites.net"
    timeout_duration = 90  # Default timeout for requests in seconds

    # To store IDs of created resources
    created_list_id = None
    created_item_id = None

    # Templates for names, will be made unique per user/run
    list_name_template = "My Awesome List"
    list_description_template = "A description for my awesome list"
    item_name_template = "Important Task"
    item_description_template = "Details about this important task"
    item_state_todo = "todo"
    item_state_in_progress = "inprogress"

    def on_start(self):
        """
        Called when a User starts.
        Initialize DEBUG_MODE and unique identifiers for this user's test data.
        """
        self.DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() == 'true'
        
        # Generate unique suffixes for names to avoid collisions
        unique_suffix = str(uuid.uuid4())[:8]
        self.current_list_name = f"{self.list_name_template} {unique_suffix}"
        self.current_list_description = f"{self.list_description_template}"
        self.current_item_name = f"{self.item_name_template} {unique_suffix}"
        self.current_item_description = f"{self.item_description_template}"

        # No specific authentication mechanism found in the HTTP file.
        # If API_KEY, BEARER_TOKEN, or Basic Auth were required,
        # checks for corresponding environment variables would be here.
        # Example:
        # self.api_key = os.getenv("API_KEY")
        # if not self.api_key:
        #     logging.error("API_KEY environment variable not set.")
        #     raise EnvironmentError("API_KEY environment variable not set.")
        # self.common_headers = {"api-key": self.api_key}

        self.common_headers = {"Accept": "application/json"}
        self.post_put_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }


    def _get_current_iso_datetime(self):
        """Generates the current datetime in ISO 8601 format."""
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    def _log_request_failure(self, response, request_name):
        """Helper function to log detailed failure information."""
        failure_msg = f"{request_name} failed with status {response.status_code}. Response: {response.text}"
        response.failure(failure_msg)
        if self.DEBUG_MODE:
            logging.error(failure_msg)
            logging.error(f"Request URL: {response.url}")
            logging.error(f"Request Headers: {response.request.headers}")
            if response.request.body:
                try:
                    # Attempt to decode as UTF-8, common for JSON
                    body_str = response.request.body.decode('utf-8')
                except UnicodeDecodeError:
                    # Fallback for binary or other encodings
                    body_str = str(response.request.body)
                logging.error(f"Request Body: {body_str}")
            else:
                logging.error("Request Body: No Body")

    @task
    def run_scenario(self):
        """
        Main task defining the sequence of API calls.
        """
        logging.info("Starting API scenario run...")
        self.get_all_lists()
        self.create_new_list()

        if self.created_list_id:
            self.get_specific_list_by_id()
            self.update_specific_list_by_id()
            self.get_all_items_in_list()
            self.create_new_list_item()

            if self.created_item_id:
                self.get_specific_list_item_by_id()
                self.update_specific_list_item()
                self.get_list_items_by_state()
                self.delete_specific_list_item()
                # self.created_item_id is set to None within delete_specific_list_item on success
            
            self.delete_specific_list()
            # self.created_list_id is set to None within delete_specific_list on success
        else:
            logging.warning("Skipping dependent list operations as list creation failed or was skipped.")
        
        logging.info("API scenario run finished.")


    def get_all_lists(self):
        """GET /lists - Retrieves all todo lists."""
        request_name = "Get All Lists"
        logging.info(f"Executing: {request_name}")
        with self.client.get(
            "/lists",
            headers=self.common_headers,
            name=request_name,
            catch_response=True,
            timeout=self.timeout_duration
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                self._log_request_failure(response, request_name)

    def create_new_list(self):
        """POST /lists - Creates a new todo list."""
        request_name = "Create List" # From @name createList
        logging.info(f"Executing: {request_name}")
        payload = {
            "name": self.current_list_name,
            "description": self.current_list_description
        }
        with self.client.post(
            "/lists",
            json=payload,
            headers=self.post_put_headers,
            name=request_name,
            catch_response=True,
            timeout=self.timeout_duration
        ) as response:
            if response.status_code == 201: # Typically 201 Created for POST
                response.success()
                try:
                    self.created_list_id = response.json().get("id")
                    if not self.created_list_id:
                        logging.error(f"{request_name}: 'id' not found in response JSON: {response.text}")
                        # No response.failure() here as request was 201, but data is missing
                    else:
                        logging.info(f"{request_name}: Created list with ID: {self.created_list_id}")
                except json.JSONDecodeError:
                    logging.error(f"{request_name}: Failed to parse JSON response: {response.text}")
                    # No response.failure() here as request was 201
            else:
                self._log_request_failure(response, request_name)
                self.created_list_id = None # Ensure it's None if creation failed

    def get_specific_list_by_id(self):
        """GET /lists/{listId} - Retrieves a specific list."""
        if not self.created_list_id:
            logging.warning("Skipping Get Specific List: created_list_id is not set.")
            return

        request_name = "Get List by ID"
        logging.info(f"Executing: {request_name} (ID: {self.created_list_id})")
        url = f"/lists/{self.created_list_id}"
        with self.client.get(
            url,
            headers=self.common_headers,
            name=f"{request_name}", # Dynamic name for better reporting if needed
            catch_response=True,
            timeout=self.timeout_duration
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                self._log_request_failure(response, request_name)

    def update_specific_list_by_id(self):
        """PUT /lists/{listId} - Updates a specific list."""
        if not self.created_list_id:
            logging.warning("Skipping Update Specific List: created_list_id is not set.")
            return

        request_name = "Update List by ID"
        logging.info(f"Executing: {request_name} (ID: {self.created_list_id})")
        url = f"/lists/{self.created_list_id}"
        payload = {
            "name": f"{self.current_list_name} - Updated",
            "description": f"{self.current_list_description} - Updated"
        }
        with self.client.put(
            url,
            json=payload,
            headers=self.post_put_headers,
            name=f"{request_name}",
            catch_response=True,
            timeout=self.timeout_duration
        ) as response:
            if response.status_code == 200: # Or 204 No Content if API returns that
                response.success()
            else:
                self._log_request_failure(response, request_name)

    def get_all_items_in_list(self):
        """GET /lists/{listId}/items - Retrieves all items in a list."""
        if not self.created_list_id:
            logging.warning("Skipping Get All Items in List: created_list_id is not set.")
            return

        request_name = "Get All Items in List"
        logging.info(f"Executing: {request_name} (List ID: {self.created_list_id})")
        url = f"/lists/{self.created_list_id}/items"
        with self.client.get(
            url,
            headers=self.common_headers,
            name=f"{request_name}",
            catch_response=True,
            timeout=self.timeout_duration
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                self._log_request_failure(response, request_name)

    def create_new_list_item(self):
        """POST /lists/{listId}/items - Creates a new item in a list."""
        if not self.created_list_id:
            logging.warning("Skipping Create New List Item: created_list_id is not set.")
            return

        request_name = "Create List Item" # From @name createListItem
        logging.info(f"Executing: {request_name} (List ID: {self.created_list_id})")
        url = f"/lists/{self.created_list_id}/items"
        payload = {
            "name": self.current_item_name,
            "state": self.item_state_todo,
            "dueDate": self._get_current_iso_datetime(),
            "description": self.current_item_description
        }
        with self.client.post(
            url,
            json=payload,
            headers=self.post_put_headers,
            name=request_name,
            catch_response=True,
            timeout=self.timeout_duration
        ) as response:
            if response.status_code == 201:
                response.success()
                try:
                    self.created_item_id = response.json().get("id")
                    if not self.created_item_id:
                        logging.error(f"{request_name}: 'id' not found in item response JSON: {response.text}")
                    else:
                        logging.info(f"{request_name}: Created item with ID: {self.created_item_id}")
                except json.JSONDecodeError:
                    logging.error(f"{request_name}: Failed to parse JSON response for item: {response.text}")
            else:
                self._log_request_failure(response, request_name)
                self.created_item_id = None # Ensure it's None if creation failed

    def get_specific_list_item_by_id(self):
        """GET /lists/{listId}/items/{itemId} - Retrieves a specific item."""
        if not self.created_list_id or not self.created_item_id:
            logging.warning("Skipping Get Specific List Item: created_list_id or created_item_id is not set.")
            return

        request_name = "Get List Item by ID"
        logging.info(f"Executing: {request_name} (List ID: {self.created_list_id}, Item ID: {self.created_item_id})")
        url = f"/lists/{self.created_list_id}/items/{self.created_item_id}"
        with self.client.get(
            url,
            headers=self.common_headers,
            name=f"{request_name}",
            catch_response=True,
            timeout=self.timeout_duration
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                self._log_request_failure(response, request_name)

    def update_specific_list_item(self):
        """PUT /lists/{listId}/items/{itemId} - Updates a specific item."""
        if not self.created_list_id or not self.created_item_id:
            logging.warning("Skipping Update Specific List Item: created_list_id or created_item_id is not set.")
            return

        request_name = "Update List Item"
        logging.info(f"Executing: {request_name} (List ID: {self.created_list_id}, Item ID: {self.created_item_id})")
        url = f"/lists/{self.created_list_id}/items/{self.created_item_id}"
        payload = {
            "name": f"{self.current_item_name} - Updated",
            "state": self.item_state_in_progress,
            "dueDate": self._get_current_iso_datetime(),
            "completedDate": None, # As per HTTP file
            "description": f"{self.current_item_description} - Updated"
        }
        with self.client.put(
            url,
            json=payload,
            headers=self.post_put_headers,
            name=f"{request_name}",
            catch_response=True,
            timeout=self.timeout_duration
        ) as response:
            if response.status_code == 200: # Or 204
                response.success()
            else:
                self._log_request_failure(response, request_name)

    def get_list_items_by_state(self):
        """GET /lists/{listId}/state/{state} - Retrieves items by state."""
        if not self.created_list_id:
            logging.warning("Skipping Get List Items by State: created_list_id is not set.")
            return

        request_name = "Get List Items by State"
        state_to_query = self.item_state_in_progress # As per HTTP file example
        logging.info(f"Executing: {request_name} (List ID: {self.created_list_id}, State: {state_to_query})")
        url = f"/lists/{self.created_list_id}/state/{state_to_query}"
        with self.client.get(
            url,
            headers=self.common_headers,
            name=f"{request_name}",
            catch_response=True,
            timeout=self.timeout_duration
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                self._log_request_failure(response, request_name)

    def delete_specific_list_item(self):
        """DELETE /lists/{listId}/items/{itemId} - Deletes a specific item."""
        if not self.created_list_id or not self.created_item_id:
            logging.warning("Skipping Delete Specific List Item: created_list_id or created_item_id is not set.")
            return

        request_name = "Delete List Item"
        logging.info(f"Executing: {request_name} (List ID: {self.created_list_id}, Item ID: {self.created_item_id})")
        url = f"/lists/{self.created_list_id}/items/{self.created_item_id}"
        with self.client.delete(
            url,
            headers=self.common_headers,
            name=f"{request_name}",
            catch_response=True,
            timeout=self.timeout_duration
        ) as response:
            if response.status_code in [200, 204]: # 204 No Content is common for DELETE
                response.success()
                logging.info(f"{request_name}: Successfully deleted item ID: {self.created_item_id}")
                self.created_item_id = None # Clear ID after successful deletion
            else:
                self._log_request_failure(response, request_name)

    def delete_specific_list(self):
        """DELETE /lists/{listId} - Deletes a specific list."""
        if not self.created_list_id:
            logging.warning("Skipping Delete Specific List: created_list_id is not set.")
            return

        request_name = "Delete List"
        logging.info(f"Executing: {request_name} (ID: {self.created_list_id})")
        url = f"/lists/{self.created_list_id}"
        with self.client.delete(
            url,
            headers=self.common_headers,
            name=f"{request_name}",
            catch_response=True,
            timeout=self.timeout_duration
        ) as response:
            if response.status_code in [200, 204]:
                response.success()
                logging.info(f"{request_name}: Successfully deleted list ID: {self.created_list_id}")
                self.created_list_id = None # Clear ID after successful deletion
            else:
                self._log_request_failure(response, request_name)

    def _cleanup_item(self, list_id, item_id):
        """Helper to delete an item during on_stop."""
        if not list_id or not item_id:
            return
        logging.info(f"on_stop: Attempting to clean up item {item_id} from list {list_id}")
        url = f"/lists/{list_id}/items/{item_id}"
        # This request is for cleanup, not part of main stats unless explicitly named
        # For simplicity, using self.client which will report it if named.
        # To avoid reporting, use a separate requests.Session() or similar.
        resp = self.client.delete(url, headers=self.common_headers, name="Cleanup Delete Item", timeout=self.timeout_duration)
        if resp.status_code in [200, 204]:
            logging.info(f"on_stop: Successfully cleaned up item {item_id}.")
        else:
            logging.warning(f"on_stop: Failed to clean up item {item_id}. Status: {resp.status_code}, Response: {resp.text}")


    def _cleanup_list(self, list_id):
        """Helper to delete a list during on_stop."""
        if not list_id:
            return
        logging.info(f"on_stop: Attempting to clean up list {list_id}")
        url = f"/lists/{list_id}"
        resp = self.client.delete(url, headers=self.common_headers, name="Cleanup Delete List", timeout=self.timeout_duration)
        if resp.status_code in [200, 204]:
            logging.info(f"on_stop: Successfully cleaned up list {list_id}.")
        else:
            logging.warning(f"on_stop: Failed to clean up list {list_id}. Status: {resp.status_code}, Response: {resp.text}")

    def on_stop(self):
        """
        Called when a User stops.
        Attempt to clean up any resources created by this user if they still exist.
        The main scenario attempts to delete these, so this is a fallback.
        """
        logging.info("Executing on_stop: Cleaning up resources...")
        if self.created_item_id and self.created_list_id:
            # If item exists, it must be deleted before its list (usually)
            self._cleanup_item(self.created_list_id, self.created_item_id)
        
        if self.created_list_id:
            self._cleanup_list(self.created_list_id)
        
        logging.info("on_stop: Cleanup finished.")

# To run this test locally:
# locust -f your_locust_script_name.py -u 1 -r 1 --run-time 30s
# Example: locust -f locustfile.py -u 10 -r 2 --run-time 1m

# To run with DEBUG_MODE enabled (for detailed error logs):
# DEBUG_MODE=True locust -f locustfile.py ...