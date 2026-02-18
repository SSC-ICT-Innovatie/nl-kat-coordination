INSERT INTO public.django_content_type (app_label, model) VALUES
  ('crisis_room', 'dashboarditem'),
  ('crisis_room', 'dashboard'),
  ('tools', 'organizationtag'),
  ('account', 'katuser'),
  ('account', 'authtoken'),
  ('knox', 'authtoken')
ON CONFLICT DO NOTHING;

-- Note: this list was generated with the following query, dumping it here in case we need to dig it up again:
-- SELECT a.name, a.codename, d.app_label, d.model FROM auth_permission a
-- JOIN django_content_type d ON a.content_type_id = d.id
-- WHERE codename IN (
-- 'add_authtoken', 'add_dashboard', 'add_dashboarditem', 'add_organizationtag', 'can_access_all_organizations',
-- 'can_add_boefje', 'change_authtoken', 'change_dashboard', 'change_dashboarditem', 'change_dashboarditem_position',
-- 'change_organizationtag', 'delete_authtoken', 'delete_dashboard', 'delete_dashboarditem', 'delete_organizationtag',
-- 'view_authtoken', 'view_dashboard', 'view_dashboarditem', 'view_organizationtag');

INSERT INTO public.auth_permission (name, content_type_id, codename) VALUES
('Can add auth token', (select id from public.django_content_type where model = 'authtoken' and app_label = 'account'),'add_authtoken'),
('Can change auth token', (select id from public.django_content_type where model = 'authtoken' and app_label = 'account'),'change_authtoken'),
('Can delete auth token', (select id from public.django_content_type where model = 'authtoken' and app_label = 'account'),'delete_authtoken'),
('Can view auth token', (select id from public.django_content_type where model = 'authtoken' and app_label = 'account'),'view_authtoken'),
('Can add dashboard', (select id from public.django_content_type where model = 'dashboard' and app_label = 'crisis_room'),'add_dashboard'),
('Can change dashboard', (select id from public.django_content_type where model = 'dashboard' and app_label = 'crisis_room'),'change_dashboard'),
('Can delete dashboard', (select id from public.django_content_type where model = 'dashboard' and app_label = 'crisis_room'),'delete_dashboard'),
('Can view dashboard', (select id from public.django_content_type where model = 'dashboard' and app_label = 'crisis_room'),'view_dashboard'),
('Can add organization tag', (select id from public.django_content_type where model = 'organizationtag' and app_label = 'tools'),'add_organizationtag'),
('Can change organization tag', (select id from public.django_content_type where model = 'organizationtag' and app_label = 'tools'),'change_organizationtag'),
('Can delete organization tag', (select id from public.django_content_type where model = 'organizationtag' and app_label = 'tools'),'delete_organizationtag'),
('Can view organization tag', (select id from public.django_content_type where model = 'organizationtag' and app_label = 'tools'),'view_organizationtag'),
('Can add new or duplicate boefjes', (select id from public.django_content_type where model = 'organization' and app_label = 'tools'),'can_add_boefje'),
('Can access all organizations', (select id from public.django_content_type where model = 'organization' and app_label = 'tools'),'can_access_all_organizations'),
('Can add dashboard item', (select id from public.django_content_type where model = 'dashboarditem' and app_label = 'crisis_room'),'add_dashboarditem'),
('Can change dashboard item', (select id from public.django_content_type where model = 'dashboarditem' and app_label = 'crisis_room'),'change_dashboarditem'),
('Can change position up or down of a dashboard item.', (select id from public.django_content_type where model = 'dashboarditem' and app_label = 'crisis_room'),'change_dashboarditem_position'),
('Can delete dashboard item', (select id from public.django_content_type where model = 'dashboarditem' and app_label = 'crisis_room'),'delete_dashboarditem'),
('Can view dashboard item', (select id from public.django_content_type where model = 'dashboarditem' and app_label = 'crisis_room'),'view_dashboarditem'),
('Can add auth token', (select id from public.django_content_type where model = 'authtoken' and app_label = 'knox'),'add_authtoken'),
('Can change auth token', (select id from public.django_content_type where model = 'authtoken' and app_label = 'knox'),'change_authtoken'),
('Can delete auth token', (select id from public.django_content_type where model = 'authtoken' and app_label = 'knox'),'delete_authtoken'),
('Can view auth token', (select id from public.django_content_type where model = 'authtoken' and app_label = 'knox'),'view_authtoken')
ON CONFLICT DO NOTHING;
