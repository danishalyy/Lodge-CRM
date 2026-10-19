export type ModuleKey = 'dashboard'|'guests'|'stays'|'rooms'|'requests'|'feedback'|'staff'|'hr'|'roles'|'departments'|'tasks'|'housekeeping'|'maintenance'|'food-beverage'|'activities'|'transfers'|'fleet'|'fuel'|'wildlife'|'ranger'|'reports'|'memory'|'lodge-ai'|'notifications'|'settings';

export const modules = [
  ['dashboard','Command Centre','◫'],['guests','Guest CRM','◎'],['stays','Stays','◌'],['rooms','Rooms & Units','▦'],['requests','Guest Requests','✦'],['feedback','Guest Feedback','★'],
  ['staff','Staff','♙'],['hr','Staff HR','▤'],['roles','Roles & Permissions','⌘'],['departments','Departments','⌘'],['tasks','Tasks','✓'],['housekeeping','Housekeeping','⌂'],['maintenance','Maintenance','⚙'],['food-beverage','Food & Beverage','◍'],
  ['activities','Activities','◈'],['transfers','Transfers','↔'],['ranger','Ranger View','♞'],['fleet','Fleet','◇'],['fuel','Fuel','◒'],['wildlife','Wildlife','⌖'],['reports','Reports','▥'],['memory','Operational Memory','◷'],
  ['lodge-ai','Ask Lodge AI','✧'],['notifications','Notifications','◉'],['settings','Account Security','⚙']
] as const;

// The server-returned entitlement list is the source of truth. This map only connects a UI module to its server feature key.
export const moduleFeature:Partial<Record<ModuleKey,string>>={
 dashboard:'dashboard',guests:'guests',stays:'stays',rooms:'units',requests:'guest_requests',feedback:'guest_feedback',staff:'staff',hr:'staff_hr',roles:'custom_roles',departments:'departments',tasks:'tasks',housekeeping:'housekeeping',maintenance:'maintenance','food-beverage':'fb_operations',activities:'activities',transfers:'transfers',ranger:'ranger',fleet:'fleet',fuel:'fuel',wildlife:'wildlife',reports:'reports',notifications:'notifications','lodge-ai':'ai'
};
