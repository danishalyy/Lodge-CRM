export type ModuleKey = 'dashboard'|'guests'|'stays'|'rooms'|'requests'|'feedback'|'staff'|'hr'|'roles'|'departments'|'tasks'|'housekeeping'|'maintenance'|'food-beverage'|'activities'|'transfers'|'fleet'|'fuel'|'wildlife'|'ranger'|'reports'|'memory'|'lodge-ai'|'notifications'|'settings';

export const modules = [
  ['dashboard','Home','◫'],['guests','Guests','◎'],['stays','Stays','◌'],['rooms','Rooms & Units','▦'],['requests','Guest Requests','✦'],['feedback','Feedback','★'],
  ['staff','Staff','♙'],['hr','Staff Records','▤'],['roles','Roles & Access','⌘'],['departments','Departments','⌘'],['tasks','Tasks','✓'],['housekeeping','Housekeeping','⌂'],['maintenance','Maintenance','⚙'],['food-beverage','Food & Beverage','◍'],
  ['activities','Activities','◈'],['transfers','Transfers','↔'],['ranger','Ranger Schedule','♞'],['fleet','Fleet','◇'],['fuel','Fuel','◒'],['wildlife','Wildlife','⌖'],['reports','Reports','▥'],['memory','Activity History','◷'],
  ['lodge-ai','Ask Lodge AI','✧'],['notifications','Notifications','◉'],['settings','Account Security','⚙']
] as const;

// The server-returned entitlement list is the source of truth. This map only connects a UI module to its server feature key.
export const moduleFeature:Partial<Record<ModuleKey,string>>={
 dashboard:'dashboard',guests:'guests',stays:'stays',rooms:'units',requests:'guest_requests',feedback:'guest_feedback',staff:'staff',hr:'staff_hr',roles:'custom_roles',departments:'departments',tasks:'tasks',housekeeping:'housekeeping',maintenance:'maintenance','food-beverage':'fb_operations',activities:'activities',transfers:'transfers',ranger:'ranger',fleet:'fleet',fuel:'fuel',wildlife:'wildlife',reports:'reports',notifications:'notifications','lodge-ai':'ai'
};
