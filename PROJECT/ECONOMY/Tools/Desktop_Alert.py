from plyer import notification

# This function sends the actual alert to your desktop
notification.notify(
    title = 'Python Alert Test',
    message = 'If you see this, your notifications are working!',
    app_icon = None,  # You can add a path to an .ico file here later
    timeout = 10,      # The alert stays visible for 10 seconds
)