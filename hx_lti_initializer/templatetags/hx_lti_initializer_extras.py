from django.template.defaulttags import register
from django.conf import settings
from datetime import datetime
from dateutil import tz
from django import template
from django.template.defaultfilters import stringfilter
from django.contrib.staticfiles.templatetags.staticfiles import static
from re import sub

from hx_lti_assignment.models import Assignment
from abstract_base_classes.target_object_database_api import TOD_Implementation
from target_object_database.models import TargetObject

def convert_tz(datetimeobj):
	'''
		Converts a datetimeobj from UTC to the local timezone
	'''
	from_zone = tz.tzutc()
	to_zone = tz.gettz('America/New_York')
	# Tell datetime object it's in UTC
	utc = datetimeobj.replace(tzinfo=from_zone)
	# Convert to local time
	local = utc.astimezone(to_zone)

	return local

@register.filter
def format_date(str):
	'''
		Converts a date string into a more readable format
	'''
	
	# Check for None case
	if str is None:
		return ""

	# Clean string by stripping all non numeric characters
	cleaned = sub("[^0-9]", "", str)

	try:
		# Store formatted date as datetimeobject and convert timezone
		dformatted = convert_tz(datetime.strptime(cleaned, "%Y%m%d%H%M%S"))
		# Date string in format for display on webpage
		date = dformatted.strftime('%b %d')
	except ValueError:
		date = str

	return date
			
@register.filter
def format_tags(tagslist):
	'''
		Pretty-prints list of tags
	'''
	return ', '.join(tagslist)
	
@register.simple_tag
def get_assignment_name(collection_id):
	# Filter for the assignment with assignment_id matching collection_id
	try:
		assignment = Assignment.objects.get(assignment_id=collection_id);
		return unicode(assignment)
	# TODO: Currently fails silently. Eventually we will want to improve the model design so this doesn't happen.
	except:
		return ''

@register.simple_tag
def get_target_object_name(object_id):
	try:
		targ_obj = TargetObject.objects.get(pk=object_id)
		return unicode(targ_obj)
	# TODO: Currently fails silently. Eventually we will want to improve the model design so this doesn't happen.
	except:
		return ''

@register.assignment_tag
def assignment_object_exists(media_type, object_id, collection_id):
	'''
		Checks to make sure that both the object exists in the assignment.
		- In the case of text objects, both the assignment and target object must exist.
		- In the case of image objects, we just check the assignment exists because the object ID is
		  the canvas ID from the IIIF manifest, which we have not saved and therefore can't easily check.
	'''
	object_exists = False
	if media_type == 'image':
		object_exists = Assignment.objects.filter(assignment_id=collection_id).exists()
	else:
		target_object_exists = TargetObject.objects.filter(pk=object_id).exists()
		assignment_exists = Assignment.objects.filter(assignment_id=collection_id).exists()
		object_exists = target_object_exists and assignment_exists
	return object_exists

@register.simple_tag
def get_annotation_selection(media_type, annotation):
	'''
	Returns the selection of the target object that has been annotated,
	whether that's a region of an image (represented as a thumbnail image),
	or line(s) of text.
	'''
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
def get_annotation_by_id(annotation_id, annotations):
	'''
		Given the id of an annotation and a dictionary of annotations keyed by id,
		this returns the text of the annotation with that id	
	'''
	annotation_id = int(annotation_id)
	if annotation_id in annotations:
		return annotations[annotation_id]['text']
	return '<i>Deleted Annotation</i>'

@register.simple_tag
def get_url_to_annotation_manual(**kwargs):
	'''
	Returns the URL to the annotation manual. When the URL is present in the django settings,
	it returns this URL, otherwise it will return the static url passed in to this function.
	'''
	url = kwargs.get('default', '')
	if settings.ANNOTATION_MANUAL_URL is not None:
		url = settings.ANNOTATION_MANUAL_URL
	if not url.startswith('http'):
		url = static(url)
	return url
	