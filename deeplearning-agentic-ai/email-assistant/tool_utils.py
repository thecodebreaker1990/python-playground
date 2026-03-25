from datetime import datetime

def get_current_time():
    """
    Returns the current time as a string
    """
    return datetime.now().strftime("%H:%M:%S")



