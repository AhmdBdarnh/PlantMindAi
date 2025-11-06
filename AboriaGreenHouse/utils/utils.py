
# Enable or disable serial logging
serial_log_enabled = False

def set_serial_log_enabled(enabled):
    """Enable or disable serial logging"""
    global serial_log_enabled
    serial_log_enabled = enabled

# Custom print function to handle output
def _CUSTOM_PRINT_FUNC(message, end='\n'):
    global serial_log_enabled
    """Custom print function to handle output"""
    if not serial_log_enabled:
        print(message, end=end)
    # You can also log this message to a file or a logging system if needed