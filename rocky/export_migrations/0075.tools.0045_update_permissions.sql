INSERT INTO public.auth_permission (name, content_type_id, codename) VALUES (
                                                                              'Can enable or disable schedules',
                                                                              (select id from public.django_content_type where model = 'organization'),
                                                                              'can_enable_disable_schedule'
                                                                            ) ON CONFLICT DO NOTHING;

INSERT INTO public.auth_group_permissions (group_id, permission_id) VALUES (
                                                                             (select id from public.auth_group where name = 'admin'),
                                                                             (select id from public.auth_permission where codename = 'can_enable_disable_schedule')
                                                                           ) ON CONFLICT DO NOTHING;

INSERT INTO public.auth_group_permissions (group_id, permission_id) VALUES (
                                                                             (select id from public.auth_group where name = 'redteam'),
                                                                             (select id from public.auth_permission where codename = 'can_enable_disable_schedule')
                                                                           ) ON CONFLICT DO NOTHING;
