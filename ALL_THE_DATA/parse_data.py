import json
import base64

with open("/home/punk/Projects/packetfs/ALL_THE_DATA/agent_tasks.json") as f:
    x = json.loads(f.read())
    for line in x:

        print(base64.b64decode(line["task"].encode("utf-8")))
        break
    


    
