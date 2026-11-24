Set up tm1cm for me: a tool that moves IBM Planning Analytics (TM1) models between servers and files, one file per object, for git.

Before you change anything, ask me which TM1 servers I have (the environments, such as test and prod), and the address of each one's REST API, unless I've said already. Ask how I log in: TM1's own security, or CAM, and which namespace. Never write a password into a file: tm1cm asks for it when it connects. Never put anything on a server without asking me first.

1. Check Python {{python}} or newer and git are installed.
2. Install tm1cm: {{install}}
3. Make the project with tm1cm --mode scaffold --path <folder>, and set base_url in config/<environment>/connect.yaml and user (and namespace, for CAM) in config/default/credentials.yaml, for each environment.
4. Get the model from the first environment with tm1cm --mode get --environment <environment>, show me what it wrote under data/, and commit it to git.
5. These walkthroughs do each step, with what tm1cm prints:

{{walkthroughs}}

6. Look up each setting, filter and option in the reference: {{docs}}. Everything is also in one file for agents: {{llms-full}}
