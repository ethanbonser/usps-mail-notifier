import functions_framework
from scripts.check_mail import check_usps_mail, load_history

@functions_framework.http
def check_mail_http(request):
    """HTTP Cloud Function to check USPS mail.
    Args:
        request (flask.Request): The request object.
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`.
    """
    load_history()
    success = check_usps_mail(is_automatic=True)
    if success:
        return "Mail check completed: New mail found.", 200
    else:
        return "Mail check completed: No new mail.", 200
