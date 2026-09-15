# Testing the boefje

First, we run `make kat`. After that successfully finishes. You can run `grep 'DJANGO_SUPERUSER_PASSWORD' .env` to get the password for the super user. The login e-mail is `superuser@localhost`.

After logging in, OpenKAT will guide you through their first-time setup.

1. Click the "Let's get started" button.
2. Input the name of your company (or just any name since this is a test run)
3. Also input a short code which will be used to identify your company on the back-end
4. On the next page give indemnification on the organization and declare that you as a person can be held accountable.
5. Press the "Continue with this account, onboard me!" button
6. And then you can press on the "Skip onboarding" button to finish the setup.
7. After that in the top left corner you can select your company.

We recommend that you at least once go through the onboarding process before developing your boefje.

8. Now we want to enable our boefje, for this we will need to go to the KAT-alogus (in the navigation bar at the top) and look for our boefje and enable it.
9. If you followed the steps correctly, you should see two text inputs being requested from you. In the first one, you can put in any text that you want to be part of the boefje's greeting. As you might remember the second input is asking for an integer between 0 and 9 (you can see the description of the text inputs by pressing the question mark to the right of the text input.)
10. After having made your choice you can press the "Add settings and enable boefje" button.
11. Now it should say that the boefje has been enabled, but if we go to the Tasks page (in the navigation bar at the top) we see that the boefje is currently not doing anything. This is because our boefje will only run if a valid IPAddressV4 or IPAddressV6 OOI is available. Let's create one of those by using existing boefjes and normalizers.

If you do not want to go through the trouble of seeing existing boefjes and normalizers to work you can go to Objects > Add new object > Object type: _IPAddressV4_ > Insert an IPv4 address for which you have an indemnification, and choose as network _Network|internet_ and then skip to step 19 of this tutorial.

12. Enable the "DnsRecords" boefje. This boefje takes in a hostname and makes a DNS-record from it.
13. Let's add a URL OOI. Go to Objects (in the navigation bar at the top) and on the right you will see an "Add" button. After pressing this button press the "Add object" button.
14. As an object type we will choose URL.
15. As a network for the URL we will select the internet ("Network|internet") and now we have to give it a website URL. For this example, we can use "https://mispo.es/" and then press the "add url" button.
16. If we now go to the Tasks tab, we will see that still no boefjes are being run. This is because our URL has too low of a clearance level. Go to the tab Objects and select the "mispo.es" OOI by pressing the checkbox in front of it. Then you can change the clearance level on the bottom of the page. To be able to get an IPAddressV4 OOI from this object, we will need to give it a clearance level of L1 or higher. For this example let's set it to L2.
17. After doing this we can go to the Tasks tab and see that boefjes have started running on our provided OOI. Now the "DnsRecords" boefje will make a raw file (of type "boefje/dns-records") and the "Dns Normalize" normalizer will obtain an IPAddressV4 or IPAddressV6 from this (you can see the normalizers task by going to the tab Tasks and then switching from Boefjes to the Normalizers tab.)
18. If we now go to the Objects tab. We can see that a lot more OOIs have been added. And also among other things, we can see IPAddressV4s being added. This means our boefje should run too.
19. After IPAddressV4 or IPAddressV6 OOIs have been added. Our boefje should immediately be queued to run from it. We can see this by going into the Tasks tab again. If you see a boefje called "Hello Katty" being run with a completed status then congratulations! Your first boefje has officially run! If your boefje or normalizer fails, you can download the raw files and see what went wrong.
20. We can now open the task with the arrow button on the right and if we then press the "Download meta and raw data" it will install a zip file with 2 files inside.
    - **meta file**: The json file contains meta data that our boefje has received. The `boefje_meta` object has been given to our `run` method as a parameter.
    - **raw file**: The other file without extension contains the information our boefje has returned. In our case it should contain a json as a single line string. You can open this file with any text editor to check it out. This data will be available for the normalizers that consume raw data with the type `boefje/hello-katty`.

Now that we have a way to generate the data for normalizers, we need to create a new type of OOI that the normalizer should generate from this raw data. So let's do that!
