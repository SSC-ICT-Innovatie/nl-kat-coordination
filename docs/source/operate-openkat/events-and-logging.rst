==================
Events and Logging
==================

For Events we use CRUDE (create, read, update, delete, execute) as specified in the NEN7513.

Different routes have different ranges of Event Codes, the ranges are as follows:

- login_event: 0900** & 09XXXXX, where XXXX = 1111, 2222, 3333 etc.
- file_action: 7000**
- ooi_change: 80000* - 80001* & 10050* & 90023*
- plugin_change: 80002* - 80003*
- job_change: 80005*
- report_change: 80007*
- schedule_change 80008*
- report_recipe_change 80009*
- dashboard_change 90030*
- dashboarddata_change 90030*
- account_change: 9001**
- organization_change: 90020* 0 90021* & 9*0000
- indemnification_change: 90022*
- observation_change: 10010*
- declaration_change: 10020*
- affirmation_change: 10030*
- origin_change: 10040*

========== ================== ====================== =========================================== =====
Event code Model              Routing key            Description                                 CRUDE
========== ================== ====================== =========================================== =====
090001     Session            login_event            A session is created.                       C
090002     Session            login_event            A session updated.                          U
090003     Session            login_event            A session is deleted.                       D
091111     KATUser            login_event            A user logged in.                           E
092222     KATUser            login_event            A user logged out.                          E
093333     TOTPDevice         login_event            A user MFA failed.                          E
094444     KATUser            login_event            A user login failed.                        E
700001     RawData            file_action            A raw file is downloaded.                   E
800010     ScanProfile        ooi_change             A scan profile is (re)declared.             U
800011     ScanProfile        ooi_change             A scan profile set to empty.                D
800021     Plugin             plugin_change          A plugin is enabled.                        U
800022     Plugin             plugin_change          A plugin is disabled.                       U
800023     Plugin             plugin_change          Settings of a plugin are updated.           U
800024     Plugin             plugin_change          Settings of a plugin are deleted.           D
800025     Plugin             plugin_change          A plugin is created.                        C
800026     Plugin             plugin_change          A plugin is updated.                        U
800051     Job                job_change             A job is manually created.                  C
800071     Report             report_change          A report is created.                        C
800073     Report             report_change          A report is deleted.                        D
800081     Schedule           schedule_change        A schedule is created.                      C
800082     Schedule           schedule_change        A schedule is edited.                       U
800083     Schedule           schedule_change        A schedule is deleted.                      D
800091     ReportRecipe       report_recipe_change   A Report Recipe is created.                 C
900100     KATUser            account_change         A new user created.                         C
900101     KATUser            account_change         User data changed.                          U
900104     KATUser            account_change         Account status changed (Enabled/Disabled).  U
900105     KATUser            account_change         User credential reset is performed.         E
900106     OrganizationMember account_change         User organization membership changed.       U
900108     Indemnification    account_change         Set trusted clearance level.                U
900109     Indemnification    account_change         Set accepted clearance level.               U
900110     KATUser            account_change         A user is deleted.                          D
900111     TOTPDevice         account_change         2FA is removed.                             D
900112     TOTPDevice         account_change         2FA is updated.                             U
900201     Organization       organization_change    A new organization is created.              C
900202     Organization       organization_change    Organization information changed.           U
900203     Organization       organization_change    Organization is removed.                    D
900211     OrganizationMember organization_change    User organization membership created.       C
900212     OrganizationMember organization_change    User organization membership changed.       U
900213     OrganizationMember organization_change    User organization membership removed.       D
900221     Indemnification    indemnification_change An indemnification is created.              C
900222     Indemnification    indemnification_change An indemnification changed.                 U
900223     Indemnification    indemnification_change An indemnification is removed.              D
900231     OOIInformation     ooi_change             OOI information is created.                 C
900232     OOIInformation     ooi_change             OOI information changed.                    U
900233     OOIInformation     ooi_change             OOI information is removed.                 D
900301     Dashboard          dashboard_change       A Dashboard is created.                     C
900302     Dashboard          dashboard_change       A Dashboard is edited.                      U
900303     Dashboard          dashboard_change       A Dashboard is deleted.                     D
900307     DashboardItem      dashboard_item_change  A Dashboard item is created.                C
900308     DashboardItem      dashboard_item_change  A Dashboard item is edited.                 U
900309     DashboardItem      dashboard_item_change  A Dashboard item is deleted.                D
900310     DashboardItem      dashboard_item_change  A Dashboard item is repositioned.           U
910000     Organization       organization_change    An organization is cloned.                  C
920000     Organization       organization_change    Recalculated bits for organizations         U
100101     Observation        observation_change     An observation is created.                  C
100201     Declaration        declaration_change     A declaration is created.                   C
100301     Affirmation        affirmation_change     An affirmation is created.                  C
100403     Origin             origin_change          An origin is deleted.                       D
100503     OOI                ooi_change             An object is deleted.                       D
========== ================== ====================== =========================================== =====
