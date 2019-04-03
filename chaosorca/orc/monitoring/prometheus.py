import os

# Package import
import docker

docker_client = docker.from_env()
prometheus_name = 'se.kth.chaosorca.prometheus'
dir_name = os.path.dirname(os.path.abspath(__file__))

def start():
	'''Launches the prometheus container'''
	if getContainer() is not None:
		print('Prometheus container already exists')
		return

	# Create prometheus server.
	prometheus_container = docker_client.containers.run(
        'prom/prometheus:v2.8.0',
        command=['--config.file=/etc/prometheus/prometheus.yml',
      	'--storage.tsdb.path=/prometheus',
      	'--web.console.libraries=/usr/share/prometheus/console_libraries',
      	'--web.console.templates=/usr/share/prometheus/consoles'],
        detach=True,
        name=prometheus_name,
        ports={'9090': 9091}, # <inside-port>:<outside-port>
        remove=True,
        volumes={dir_name+'/prometheus/': {'bind': '/etc/prometheus/', 'mode': 'rw'}, 
        'prometheus_data': {'bind':'/prometheus', 'mode': 'rw'}})
	print('Created prometheus instance')

	# Create and connect prometheus to network.
	network = docker_client.networks.create(
		'se.kth.chaosorca.prometheus',
		attachable=True,
		driver='bridge',
		internal=True, # private network.
	)
	network.connect(prometheus_container)
	print('Created prometheus network')

	return prometheus_container

def getContainer():
	'''Returns the running container else None.'''
	try:
		return docker_client.containers.get(prometheus_name)
	except Exception:
		return None

def getNetwork():
	'''Returns the prometheus network, else None.'''
	try:
		return docker_client.networks.get(prometheus_name)
	except Exception:
		return None

def stop():
	'''Stops the prometheus instance'''
	container = getContainer()
	network = getNetwork()

	if len(network.containers) > 1:
		print('Containers still connected to network, aborting...')
		return

	# Remove container
	if container is not None:
		container.stop()
		print('Stopped prometheus')
	else:
		print('No prometheus to stop')

	# Remove network.
	if network is not None:
		network.remove()
		print('Removed prometheus network')
	else:
		print('No prometheus network stop remove')
