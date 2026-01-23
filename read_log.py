
try:
    with open('replay_pcr.log', 'r') as f:
        print(f.read())
except Exception as e:
    print(e)
