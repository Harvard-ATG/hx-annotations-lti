'''
This tag library is intended to be used for manipulating annotation objects
returned by the CATCH database.

TODO: many of these helper tags query the database on a per-annotation basis,
which is potentially really inefficient. For larger sets of annotation objects,
it would be better to pull out the database queries and use them to populate
a separate data structure that could then be used to pull out the necessary information.
'''

from django.template.defaulttags import register
from django.core.urlresolvers import reverse
from hx_lti_assignment.models import Assignment, AssignmentTargets
from target_object_database.models import TargetObject
import re

def __get_image_target_object(collection_id, uri):
    '''
    This helper function attempts to find the TargetObject for an image annotation.
    The uri is the Canvas URI, so the function attempts to find the TargetObject by the
    Manifest URI saved in the TargetObject which is related to the Assignment.
    '''
    manifest_id = re.sub(r'/canvas/[^/]+$', '', uri)
    object_filters = {
        "assignment_id": collection_id,
        "assignment_objects__target_content__startswith": manifest_id,
    }
    object_exists = Assignment.objects.filter(**object_filters).exists()
    if object_exists:
        target_object_pks = Assignment.objects.filter(**object_filters).values_list('assignment_objects__pk', flat=True)
        target_objects = TargetObject.objects.filter(pk__in=target_object_pks)
        if len(target_objects) == 1:
            return target_objects[0]
        else:
            return None
    return None


@register.simple_tag
def annotation_preview_url(annotation):
    media_type = annotation['media']
    context_id = annotation['contextId']
    collection_id = annotation['collectionId']
    preview_url = ''
    
    if media_type == 'image':
        target_object = __get_image_target_object(collection_id, annotation['uri'])
        if target_object is not None:
            preview_url = reverse('hx_lti_initializer:access_annotation_target', kwargs={
                "course_id": context_id,
                "assignment_id": collection_id,
                "object_id": target_object.id
            })
    else:
        preview_url = reverse('hx_lti_initializer:access_annotation_target', kwargs={
            "course_id": context_id,
            "assignment_id": collection_id,
            "object_id": annotation['uri'],
        })

    return preview_url

@register.simple_tag
def annotation_assignment_name(annotation):
    '''
    Returns the name of the assignment object that this annotation object belongs to.
    '''
    collection_id = annotation['collectionId']
    object_exists = Assignment.objects.filter(assignment_id=collection_id).exists()
    assignment_name = ''
    if object_exists:
        assignment = Assignment.objects.get(assignment_id=collection_id)
        assignment_name = unicode(assignment)
    return assignment_name

@register.simple_tag
def annotation_target_object_name(annotation):
    '''
    Returns the name of the target object that this annotation object belongs to.
    
    Notes:
    - For text annotations, the object_id is obtained from the "uri" attribute
    - For image annotations, the object_id is not easily obtainable. The "uri"
      attribute contains the IIIF canvas URI, which is what is being annotated. However,
      the TargetObject contains the IIIF manifest URI. We can get the manifest URI from
      the canvas URI, and search on that to find the TargetObject that the annotation belongs to.
      This technique only works if the canvas URI is a sub-path of the manifest URI. It would be
      better if the annotation object returned by the CATCH actually included the object ID like it
      does for text annotations, which would allow this code to be much simpler.
    '''
    media_type = annotation['media']
    collection_id = annotation['collectionId']
    object_id = annotation['uri']

    target_object_name = '' 
    if media_type == 'image':
        target_object = __get_image_target_object(collection_id, annotation['uri'])
        if target_object is None:
            target_object_name = ''
        else:
            target_object_name = unicode(target_object)
    else:
        object_exists = TargetObject.objects.filter(pk=object_id).exists()
        if object_exists:
            target_object = TargetObject.objects.get(pk=object_id)
            target_object_name = unicode(target_object)
    return target_object_name

@register.assignment_tag
def annotation_assignment_object_exists(annotation):
    '''
    Checks to make sure that both the object exists in the assignment.
    - In the case of text objects, both the assignment and target object must exist.
    - In the case of image objects, we just check the assignment exists because the object ID is
      the canvas ID from the IIIF manifest, which we have not saved and therefore can't easily check.
    '''
    media_type = annotation['media']
    collection_id = annotation['collectionId']
    object_id = annotation['uri']
    object_exists = False
    if media_type == 'image':
        object_exists = Assignment.objects.filter(assignment_id=collection_id).exists()
    else:
        target_object_exists = TargetObject.objects.filter(pk=object_id).exists()
        assignment_exists = Assignment.objects.filter(assignment_id=collection_id).exists()
        object_exists = target_object_exists and assignment_exists
    return object_exists

@register.simple_tag
def annotation_selection(annotation):
    '''
    Returns the selection of the target object that has been annotated,
    whether that's a region of an image (represented as a thumbnail image),
    or line(s) of text.
    '''
    media_type = annotation['media']
    annotation_target = ''
    if media_type == 'image':
        if 'rangePosition' not in annotation:
            return 'Unkown image range position'
        range_position = annotation['rangePosition']
        img_str = '<img src="{src}" style="width: {width}; height: {height}; max-height: 150px; max-width: 150px;" />'
        img_params = {
            "src": annotation['thumb'],
            "width": range_position['width'],
            "height": range_position["height"],
        }
        annotation_target = img_str.format(**img_params)
    else:
        quote_str = '"{quote}"'
        annotation_target = quote_str.format(quote=annotation['quote'])
    return annotation_target

@register.simple_tag
def annotation_lookup_by_id(annotation_id, annotation_dict):
    '''
    Given the id of an annotation and a dictionary of annotations keyed by id,
    this returns the text of the annotation with that id	
    '''
    annotation_id = int(annotation_id)
    if annotation_id in annotation_dict:
        return annotation_dict[annotation_id]['text']
    return '<i>Deleted Annotation</i>'