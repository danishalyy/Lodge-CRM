"""Presentation metadata for code-defined actions; grants always come from DB."""
SENSITIVE_CUSTOM_PERMISSIONS={'staff.manage','roles.custom.manage','departments.manage','notifications.delivery.view'}
ROLE_FEATURES={'department_manager':'departments','ranger':'ranger','driver':'transfers','fb':'fb'}
SCOPES={
 'lodge_admin':('The whole lodge','Full lodge administration; this preset cannot be assigned through staff invitations.'),
 'department_manager':('Their department','Department-scoped endpoints use their assigned department. Assign a department before using this scope.'),
 'front_office':('The whole lodge (Front Office)','Permissions control actions; this scope does not add an assigned-work or department restriction.'),
 'ranger':('Assigned work (Ranger)','Tasks and guide-specific records are assigned to this person; other permitted lists retain their endpoint-specific scope.'),
 'housekeeping':('Assigned work (Housekeeping)','Tasks and housekeeping work follow assignments; guest requests use the housekeeping scope.'),
 'maintenance':('Maintenance work','Tasks follow assignments; maintenance tickets are available to the workshop, not only the assignee.'),
 'driver':('Assigned work (Driver)','Tasks, transfers and driver-specific records follow assignments; other permitted lists keep their existing scope.'),
 'fb':('Food and drink work','Tasks follow assignments and requests follow the food-and-drink scope; permitted meal services are lodge-wide.'),
 'finance':('The whole lodge (Finance)','Permissions limit the available records; this scope does not impose a department or assignee filter.'),
 'general_staff':('Only their own work','Tasks and supported guest requests are restricted to their assigned work.'),
 'read_only':('The whole lodge (Read Only)','The preset has viewing permissions; a custom copy still uses its explicitly selected permissions.'),
}
ROLE_DESCRIPTIONS={
 'lodge_admin':'Full control of lodge operations and access, subject to the lodge subscription.',
 'department_manager':'Manages permitted work and staff within their assigned department.',
 'front_office':'Handles guest profiles, stays, rooms and guest requests.',
 'housekeeping':'Handles assigned housekeeping work and permitted guest-service records.',
 'maintenance':'Handles workshop maintenance and assigned tasks, with permitted fleet records.',
 'driver':'Handles assigned transport work and permitted vehicle and fuel records.',
 'ranger':'Handles guide activities, wildlife records and permitted safari operations.',
 'fb':'Handles food and drink services, assigned tasks and relevant guest requests.',
 'finance':'Views operational and cost-related records allowed by its actual permissions; it is not a money-only record filter.',
 'general_staff':'Basic access to assigned tasks and permitted personal work.',
 'read_only':'Views the records listed below and cannot change them with this preset.',
}
AREA_NAMES={'ai':'Lodge AI','dashboard':'Overview','guests':'Guests','stays':'Stays','units':'Rooms','requests':'Guest requests','feedback':'Guest feedback','housekeeping':'Housekeeping','maintenance':'Maintenance','staff':'Staff','tasks':'Tasks','vehicles':'Fleet','vehicle_checklists':'Vehicle checks','fuel':'Fuel','activities':'Activities','transfers':'Transfers','wildlife':'Wildlife','ranger':'Ranger tools','reports':'Reports','departments':'Departments','roles':'Roles and access','notifications':'Notifications','memory':'History','audit':'Audit history','fb':'Food and drink','lodge':'Lodge settings'}

def permission_metadata(permission):
    key=permission.key;area=key.split('.')[0]
    # Advanced actions are never implicitly included by a simple edit choice.
    level='view' if key.endswith('.view') else 'edit' if key.endswith('.manage') else 'advanced'
    return {'key':key,'description':permission.description,'label':permission.description or key.replace('.',' ').replace('_',' ').capitalize(),'area':area,'area_name':AREA_NAMES.get(area,area.replace('_',' ').title()),'level':level}
