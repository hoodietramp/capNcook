from stem import CircStatus
from stem.control import Controller

with Controller.from_port(port=9051) as controller:
    try:
        controller.authenticate()
        controller.signal("NEWNYM")

        print("All circuits have been flushed.")

        for circ in controller.get_circuits():
            if circ.status != CircStatus.BUILT:
                continue
            
            # Extract information about the entry node
            entry_fp, entry_nickname = circ.path[0]
            entry_desc = controller.get_network_status(entry_fp, None)
            entry_address = entry_desc.address if entry_desc else 'unknown'

            # Extract information about the exit node
            exit_fp, exit_nickname = circ.path[-1]
            exit_desc = controller.get_network_status(exit_fp, None)
            exit_address = exit_desc.address if exit_desc else 'unknown'

            print(f"Circuit Information:")
            print(f"Entry Node\n fingerprint: {entry_fp}\n nickname: {entry_nickname}\n address: {entry_address}")
            print(f"Exit Node\n fingerprint: {exit_fp}\n nickname: {exit_nickname}\n address: {exit_address}")
            print("=" * 50)

    except Exception as e:
        print(f"An error occurred: {e}")
