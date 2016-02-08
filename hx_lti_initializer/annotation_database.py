from django.conf import settings

def process_search_response(data, user_id=None, has_read_perm=False):
    if settings.ORGANIZATION  != "ATG":
        return data
    if user_id is None:
        return data
    if has_read_perm is True:
        return data

    # If we get here, that means the user has no special permissions (i.e instructor, staff, etc)
    # and they are using a non-HarvardX instance of the tool (i.e. ATG instance).
    # The code below checks the "read" permissions to return only the annotation(s) that the user
    # is authorized to read.
    authorized_data = {
        'total': 0,
        'limit': data['limit'],
        'offset': data['offset'],
        'rows': [],
    }

    for row in data['rows']:
        no_permissions = not ('permissions' in row and 'read' in row['permissions'])
        read_permissions = row['permissions']['read']
        if no_permissions or len(read_permissions) == 0 or user_id in read_permissions:
            authorized_data['rows'].append(row)

    authorized_data['total'] = len(authorized_data['rows'])
    
    return authorized_data