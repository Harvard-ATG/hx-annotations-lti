import json
import logging
import urllib
import urllib.parse

import requests
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from hx_lti_assignment.models import Assignment
from hx_lti_initializer.models import LTICourse
from hx_lti_initializer.utils import retrieve_token
from target_object_database.models import TargetObject

from .store import AnnotationStore

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET", "POST", "PUT", "DELETE"])
def api_root(request, annotation_id=None):
    return AnnotationStore.from_settings(request).root(annotation_id)


@require_http_methods(["GET"])
def search(request):
    return AnnotationStore.from_settings(request).search()


@csrf_exempt
@require_http_methods(["POST"])
def create(request):
    store = AnnotationStore.from_settings(request)
    response = store.create()
    if response.status_code == 200:
        store.lti_grade_passback()
    return response


# NOTE: annotator updates text annotations using the "PUT" method, while
#  image annotations are updated using the "POST" method, so this endpoint
#  will accept either request method.
@csrf_exempt
@require_http_methods(["PUT", "POST"])
def update(request, annotation_id):
    return AnnotationStore.from_settings(request).update(annotation_id)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete(request, annotation_id):
    return AnnotationStore.from_settings(request).delete(annotation_id)


@login_required
def transfer(request, instructor_only="1"):
    user_id = request.LTI["hx_user_id"]

    old_assignment_id = request.POST.get("old_assignment_id")
    new_assignment_id = request.POST.get("new_assignment_id")
    old_course_id = request.POST.get("old_course_id")
    new_course_id = request.POST.get("new_course_id")
    old_course = LTICourse.objects.get(course_id=old_course_id)
    new_course = LTICourse.objects.get(course_id=new_course_id)
    old_admins = []
    new_admins = dict()
    for ads in old_course.course_admins.all():
        old_admins.append(ads.anon_id)
    for ads in new_course.course_admins.all():
        new_admins[ads.name] = ads.anon_id

    assignment = Assignment.objects.get(assignment_id=old_assignment_id)
    object_ids = request.POST.getlist("object_ids[]")
    token = retrieve_token(
        user_id,
        assignment.annotation_database_apikey,
        assignment.annotation_database_secret_token,
    )

    types = {"ig": "image", "tx": "text", "vd": "video"}
    responses = []
    for pk in object_ids:
        obj = TargetObject.objects.get(pk=pk)
        uri = pk
        target_type = types[obj.target_type]
        if target_type == "image":
            result = requests.get(obj.target_content)
            uri = json.loads(result.text)["sequences"][0]["canvases"][0]["@id"]
        search_database_url = (
            str(assignment.annotation_database_url).strip() + "/search?"
        )
        create_database_url = (
            str(assignment.annotation_database_url).strip() + "/create"
        )
        headers = {
            "x-annotator-auth-token": token,
            "content-type": "application/json",
        }

        params = {
            "uri": uri,
            "contextId": old_course_id,
            "collectionId": old_assignment_id,
            "media": target_type,
            "limit": -1,
        }

        if str(instructor_only) == "1":
            params.update({"userid": old_admins})
        url_values = urllib.parse.urlencode(params, True)
        response = requests.get(search_database_url, headers=headers, params=url_values)
        if response.status_code == 200:
            annotations = json.loads(response.text)
            for ann in annotations["rows"]:
                ann["contextId"] = str(new_course_id)
                ann["collectionId"] = str(new_assignment_id)
                ann["id"] = None
                logger.info("annotation user_id: %s" % ann["user"]["id"])
                if ann["user"]["id"] in old_admins:
                    try:
                        if new_admins[ann["user"]["name"]]:
                            ann["user"]["id"] = new_admins[ann["user"]["name"]]
                    except Exception:
                        ann["user"]["id"] = user_id
                response2 = requests.post(
                    create_database_url, headers=headers, data=json.dumps(ann)
                )

    # logger.debug("%s" % str(request.POST.getlist('assignment_inst[]')))
    data = dict()
    return HttpResponse(json.dumps(data), content_type="application/json")


@login_required
def grade_me(request):
    user_id = request.LTI["hx_user_id"]
    context_id = request.LTI["hx_context_id"]
    collection_id = request.LTI["hx_collection_id"]
    object_id = request.LTI["hx_object_id"]

    params = {
        "source_id": object_id,
        "collection_id": collection_id,
        "context_id": context_id,
        "userid": user_id,
    }

    assignment = Assignment.objects.get(assignment_id=collection_id)
    search_database_url = str(assignment.annotation_database_url).strip()
    token = retrieve_token(
        user_id,
        assignment.annotation_database_apikey,
        assignment.annotation_database_secret_token,
    )
    headers = {
        "x-annotator-auth-token": token,
        "content-type": "application/json",
    }

    response = requests.get(
        search_database_url,
        headers=headers,
        params=urllib.parse.urlencode(params, True),
    )
    request_sent = False
    if response.status_code == 200:
        logger.info("Grade me search was made successfully %s" % str(response.url))
        annotations = json.loads(response.text)
        if annotations["total"] > 0:
            logger.info("Should get a grade back")
            store = AnnotationStore.from_settings(request)
            store.lti_grade_passback()
            request_sent = True
    return HttpResponse(
        json.dumps({"grade_request_sent": request_sent}),
        content_type="application/json",
    )
