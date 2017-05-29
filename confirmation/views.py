# -*- coding: utf-8 -*-

# Copyright: (c) 2008, Jarek Zgoda <jarek.zgoda@gmail.com>

__revision__ = '$Id: views.py 21 2008-12-05 09:21:03Z jarek.zgoda $'


from django.shortcuts import render_to_response
from django.template import RequestContext
from django.conf import settings
from django.http import HttpRequest, HttpResponse

from confirmation.models import Confirmation
from zproject.jinja2 import render_to_response


def confirm(request, confirmation_key):
    # type: (HttpRequest, str) -> HttpResponse
    confirmation_key = confirmation_key.lower()
    obj = Confirmation.objects.confirm(confirmation_key)
    confirmed = True
    if not obj:
        # confirmation failed
        confirmed = False
        try:
            # try to get the object we was supposed to confirm
            obj = Confirmation.objects.get(confirmation_key=confirmation_key)
        except Confirmation.DoesNotExist:
            pass
    ctx = {
        'object': obj,
        'confirmed': confirmed,
        'days': getattr(settings, 'EMAIL_CONFIRMATION_DAYS', 10),
        'key': confirmation_key,
        'full_name': request.GET.get("full_name", None),
        'support_email': settings.ZULIP_ADMINISTRATOR,
        'verbose_support_offers': settings.VERBOSE_SUPPORT_OFFERS,
    }
    templates = [
        'confirmation/confirm.html',
    ]
    if obj:
        # if we have an object, we can use specific template
        templates.insert(0, 'confirmation/confirm_%s.html' % (obj._meta.model_name,))
    return render_to_response(templates, ctx, request=request)



def password_auth_enabled(realm):
    # type: (Realm) -> bool
    if realm is not None:
        if realm.domain == 'zulip.com' and settings.PRODUCTION:
            # the dropbox realm is SSO only, but the unit tests still need to be
            # able to login
            return False

    for backend in django.contrib.auth.get_backends():
         if isinstance(backend, EmailAuthBackend):
             return True
         if isinstance(backend, ZulipLDAPAuthBackend):
             return True
    return False

def dev_auth_enabled():
    # type: () -> bool
    for backend in django.contrib.auth.get_backends():
        if isinstance(backend, DevAuthBackend):
            return True
    return False

def google_auth_enabled():
    # type: () -> bool
    for backend in django.contrib.auth.get_backends():
        if isinstance(backend, GoogleMobileOauth2Backend):
            return True
    return False

def common_get_active_user_by_email(email, return_data=None):
    # type: (text_type, Optional[Dict[str, Any]]) -> Optional[UserProfile]
    try:
        user_profile = get_user_profile_by_email(email)
    except UserProfile.DoesNotExist:
        return None
    if not user_profile.is_active:
        if return_data is not None:
            return_data['inactive_user'] = True
        return None
    if user_profile.realm.deactivated:
        if return_data is not None:
            return_data['inactive_realm'] = True
        return None
    return user_profile

def github_auth_enabled():
    # type: () -> bool
    for backend in django.contrib.auth.get_backends():
        if isinstance(backend, GitHubAuthBackend):
            return True
    return False

@has_request_variables
def cleanup_event_queue(request, user_profile, queue_id=REQ()):
    # type: (HttpRequest, UserProfile, text_type) -> HttpResponse
    client = get_client_descriptor(str(queue_id))
    if client is None:
        return json_error(_("Bad event queue id: %s") % (queue_id,))
    if user_profile.id != client.user_profile_id:
        return json_error(_("You are not authorized to access this queue"))
    request._log_data['extra'] = "[%s]" % (queue_id,)
    client.cleanup()
    return json_success()

@authenticated_json_post_view
def json_get_events(request, user_profile):
    # type: (HttpRequest, UserProfile) -> Union[HttpResponse, _RespondAsynchronously]
    return get_events_backend(request, user_profile, apply_markdown=True)

@asynchronous
@has_request_variables
def get_events_backend(request, user_profile, handler,
                       user_client = REQ(converter=get_client, default=None),
                       last_event_id = REQ(converter=int, default=None),
                       queue_id = REQ(default=None),
                       apply_markdown = REQ(default=False, validator=check_bool),
                       all_public_streams = REQ(default=False, validator=check_bool),
                       event_types = REQ(default=None, validator=check_list(check_string)),
                       dont_block = REQ(default=False, validator=check_bool),
                       narrow = REQ(default=[], validator=check_list(None)),
                       lifespan_secs = REQ(default=0, converter=int)):
    # type: (HttpRequest, UserProfile, BaseHandler, Optional[Client], Optional[int], Optional[List[text_type]], bool, bool, Optional[text_type], bool, Iterable[Sequence[text_type]], int) -> Union[HttpResponse, _RespondAsynchronously]
    if user_client is None:
        user_client = request.client

    events_query = dict(
        user_profile_id = user_profile.id,
        user_profile_email = user_profile.email,
        queue_id = queue_id,
        last_event_id = last_event_id,
        event_types = event_types,
        client_type_name = user_client.name,
        all_public_streams = all_public_streams,
        lifespan_secs = lifespan_secs,
        narrow = narrow,
        dont_block = dont_block,
        handler_id = handler.handler_id)

    if queue_id is None:
        events_query['new_queue_data'] = dict(
            user_profile_id = user_profile.id,
            realm_id = user_profile.realm.id,
            user_profile_email = user_profile.email,
            event_types = event_types,
            client_type_name = user_client.name,
            apply_markdown = apply_markdown,
            all_public_streams = all_public_streams,
            queue_timeout = lifespan_secs,
            last_connection_time = time.time(),
            narrow = narrow)

    result = fetch_events(events_query)
    if "extra_log_data" in result:
        request._log_data['extra'] = result["extra_log_data"]

    if result["type"] == "async":
        handler._request = request
        return RespondAsynchronously
    if result["type"] == "error":
        return json_error(result["message"])
    return json_success(result["response"])
