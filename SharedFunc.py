import time

def retry_on_connection_error(func, max_retries=5, delay=180):
    """Retries a function call up to `max_retries` times if an internet connection error occurs."""
    for attempt in range(max_retries):
        try:
            return func()  # Attempt the function execution
        except Exception as e:
            error_message = str(e).lower()
            if "err_internet_disconnected" in error_message or "connection reset" in error_message:
                print(f"Internet disconnected. Attempt {attempt + 1} of {max_retries}. Retrying in {delay // 60} minutes...")
                time.sleep(delay)  # Wait before retrying
            else:
                print(f"Error encountered: {e}. Not related to internet disconnection.")
                raise  # Raise the exception if it's unrelated to internet issues

    print("Max retries reached. Skipping operation.")
    return None  # Return None if all retries fail