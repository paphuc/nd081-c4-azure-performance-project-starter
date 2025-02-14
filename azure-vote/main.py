import logging
import os
import socket

import redis
from flask import Flask, render_template, request
from opencensus.ext.azure import metrics_exporter
from opencensus.ext.azure.log_exporter import AzureEventHandler, AzureLogHandler
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.ext.flask.flask_middleware import FlaskMiddleware
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.trace.tracer import Tracer

# App Insights
# TODO: Import required libraries for App Insights

# Logging
logger = logging.getLogger(__name__)

logger.addHandler(AzureLogHandler(
        connection_string=f'InstrumentationKey={INSTRUMENTATION_KEY}')
)
logger.addHandler(AzureEventHandler(
        connection_string=f'InstrumentationKey={INSTRUMENTATION_KEY}')
)
logger.setLevel(logging.INFO)

# Metrics
exporter = metrics_exporter.new_metrics_exporter(
        enable_standard_metrics=True,
        connection_string=f'InstrumentationKey={INSTRUMENTATION_KEY}')

# Tracing
tracer = Tracer(
        exporter=AzureExporter(
                connection_string=f'InstrumentationKey={INSTRUMENTATION_KEY}'),
        sampler=ProbabilitySampler(1.0),
)

app = Flask(__name__)

# Requests
middleware = FlaskMiddleware(
        app,
        exporter=AzureExporter(connection_string=f'InstrumentationKey={INSTRUMENTATION_KEY}'),
        sampler=ProbabilitySampler(rate=1.0),
)

# Load configurations from environment or config file
app.config.from_pyfile('config_file.cfg')

if ("VOTE1VALUE" in os.environ and os.environ['VOTE1VALUE']):
    button1 = os.environ['VOTE1VALUE']
else:
    button1 = app.config['VOTE1VALUE']

if ("VOTE2VALUE" in os.environ and os.environ['VOTE2VALUE']):
    button2 = os.environ['VOTE2VALUE']
else:
    button2 = app.config['VOTE2VALUE']

if ("TITLE" in os.environ and os.environ['TITLE']):
    title = os.environ['TITLE']
else:
    title = app.config['TITLE']

# Redis Connection
redis_server = os.environ['REDIS']
try:
    if "REDIS_PWD" in os.environ:
        r = redis.StrictRedis(host=redis_server,
                              port=6379,
                              password=os.environ['REDIS_PWD'])
    else:
        r = redis.Redis(redis_server)
    r.ping()
except redis.ConnectionError:
    exit('Failed to connect to Redis, terminating.')

# Change title to host name to demo NLB
if app.config['SHOWHOST'] == "true":
    title = socket.gethostname()

# Init Redis
if not r.get(button1): r.set(button1,0)
if not r.get(button2): r.set(button2,0)

@app.route('/', methods=['GET', 'POST'])
def index():

    if request.method == 'GET':

        vote1 = r.get(button1).decode('utf-8')
        tracer.span(name='Cats')
        vote2 = r.get(button2).decode('utf-8')
        tracer.span(name='Dogs')

        # Return index with values
        return render_template("index.html", value1=int(vote1), value2=int(vote2), button1=button1, button2=button2, title=title)

    elif request.method == 'POST':

        if request.form['vote'] == 'reset':

            # Empty table and return results
            r.set(button1,0)
            r.set(button2,0)
            vote1 = r.get(button1).decode('utf-8')
            properties = {'custom_dimensions': {'Cats Vote': vote1}}
            # use logger object to log cat vote
            logger.warning('Cats', extra=properties)

            vote2 = r.get(button2).decode('utf-8')
            properties = {'custom_dimensions': {'Dogs Vote': vote2}}
            # use logger object to log dog vote
            logger.warning('Dogs', extra=properties)

            return render_template("index.html", value1=int(vote1), value2=int(vote2), button1=button1, button2=button2, title=title)

        else:

            # Insert vote result into DB
            vote = request.form['vote']
            r.incr(vote,1)

            # Get current values
            vote1 = r.get(button1).decode('utf-8')
            vote2 = r.get(button2).decode('utf-8')

            # Return results
            return render_template("index.html", value1=int(vote1), value2=int(vote2), button1=button1, button2=button2, title=title)

if __name__ == "__main__":
    # TODO: Use the statement below when running locally
    # app.run() 
    # TODO: Use the statement below before deployment to VMSS
    # app.run(host='0.0.0.0', threaded=True, debug=True) # remote
    app.run(host='0.0.0.0', threaded=True, debug=True)
