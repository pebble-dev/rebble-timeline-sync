from flask import request

import beeline
from beeline.patch import requests
from beeline.middleware.flask import HoneyMiddleware
from beeline.trace import _should_sample

from .settings import config

def _sampler(fields):
    sample_rate = 2

    route = fields.get('route', '')
    if route == 'heartbeat':
        sample_rate = 100
    elif route == 'api.sync':
        sample_rate = 10

    method = fields.get('request.method')
    if method != 'GET':
        sample_rate = 1

    response_code = fields.get('response.status_code')
    if response_code != 200:
        sample_rate = 1
    
    if _should_sample(fields.get('trace.trace_id'), sample_rate):
        return True, sample_rate
    return False, 0

def init_app(app):
    beeline.init(writekey=config['HONEYCOMB_KEY'], dataset='rws', service_name='timeline_sync', sampler_hook=_sampler)
    HoneyMiddleware(app, db_events=True)

    @app.before_request
    def before_request():
        beeline.add_context_field("route", request.endpoint)

# XXX: This maybe ought be upstreamed to Beeline.
from wrapt import wrap_function_wrapper
import beeline
import urllib.request

def _urllibopen(_urlopen, instance, args, kwargs):
    if type(args[0]) != urllib.request.Request:
        args[0] = urllib.request.Request(args[0])
    
    span = beeline.start_span(context={"meta.type": "http_client"})
    
    b = beeline.get_beeline()
    if b:
        context = b.tracer_impl.marshal_trace_context()
        if context:
            b.log("urllib lib - adding trace context to outbound request: %s", context)
            args[0].headers['X-Honeycomb-Trace'] = context
        else:
            b.log("urllib lib - no trace context found")
    
    try:
        resp = None
        beeline.add_context({
            "name": "urllib_%s" % args[0].get_method(),
            "request.method": args[0].get_method(),
            "request.uri": args[0].full_url
        })
        resp = _urlopen(*args, **kwargs)
        return resp
    except Exception as e:
        beeline.add_context({
            "request.error_type": str(type(e)),
            "request.error": beeline.internal.stringify_exception(e),
        })
        raise
    finally:
        if resp:
            beeline.add_context_field("response.status_code", resp.status)
            content_type = resp.getheader('content-type')
            if content_type:
                beeline.add_context_field("response.content_type", content_type)
            content_length = resp.getheader('content-length')
            if content_length:
                beeline.add_context_field("response.content_length", content_length)
            
        beeline.finish_span(span)

wrap_function_wrapper('urllib.request', 'urlopen', _urllibopen)
