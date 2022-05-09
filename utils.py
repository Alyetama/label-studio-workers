#!/usr/bin/env python
# coding: utf-8

import json
import os
import signal
import sys
from datetime import datetime
from pathlib import Path

import minio
import ray
import requests
from loguru import logger
from requests.structures import CaseInsensitiveDict
from tqdm import tqdm


def add_logger(current_file):
    Path('logs').mkdir(exist_ok=True)
    ts = datetime.now().strftime('%m-%d-%Y_%H.%M.%S')
    logs_file = f'logs/{Path(current_file).stem}_{ts}.log'
    logger.add(logs_file)
    return logs_file


def upload_logs(logs_file):
    client = minio.Minio(os.environ['S3_ENDPOINT'],
                         access_key=os.environ['S3_ACCESS_KEY'],
                         secret_key=os.environ['S3_SECRET_KEY'],
                         region=os.environ['S3_REGION'])
    file = Path(logs_file)
    try:
        logger.debug('Uploading logs...')
        resp = client.fput_object('logs', file.name, file)
        logger.debug(f'Uploaded log file: `{resp.object_name}`')
    except minio.error.S3Error as e:
        logger.error('Could not upload logs file!')
        logger.error(e)
    return


def keyboard_interrupt_handler(sig, _):
    logger.warning(f'KeyboardInterrupt (ID: {sig}) has been caught...')
    ray.shutdown()
    logger.warning('Terminating the session gracefully...')
    sys.exit(1)


def catch_keyboard_interrupt():
    return signal.signal(signal.SIGINT, keyboard_interrupt_handler)


def get_project_ids_str(exclude_ids: str = None) -> str:
    headers = CaseInsensitiveDict()
    headers['Content-type'] = 'application/json'
    headers['Authorization'] = f'Token {os.environ["TOKEN"]}'
    url = f'{os.environ["LS_HOST"]}/api/projects?page_size=10000'
    projects = requests.get(url, headers=headers).json()
    project_ids = sorted([project['id'] for project in projects['results']])
    project_ids = [str(p) for p in project_ids]
    if exclude_ids:
        exclude_ids = [p for p in exclude_ids.split(',')]
        project_ids = [p for p in project_ids if p not in exclude_ids]
    return ','.join(project_ids)


def api_request(url,
                method='get',
                data=None,
                verbose=False,
                return_text=False) -> dict:
    headers = CaseInsensitiveDict()
    if not method == 'get':
        headers['Content-type'] = 'application/json'
    headers['Authorization'] = f'Token {os.environ["TOKEN"]}'
    if verbose:
        request = {'url': url, 'method': method, 'data': data}
        logger.debug(f'Request: {request}')
    if method == 'get':
        resp = requests.get(url, headers=headers)
    elif method == 'post':
        resp = requests.post(url, headers=headers, data=json.dumps(data))
    elif method == 'patch':
        resp = requests.patch(url, headers=headers, data=json.dumps(data))
    if return_text:
        response = resp.text  # noqa
    else:
        response = resp.json()  # noqa
    if verbose:
        logger.debug(f'Response: {response}')
    return response


def update_model_version_in_all_projects(new_model_version):
    project_ids = get_project_ids_str().split(',')

    for project_id in tqdm(project_ids):
        project = api_request(
            f'{os.environ["LS_HOST"]}/api/projects/{project_id}')
        project.update({'model_version': new_model_version})
        project.pop('created_by')

        patched_project = api_request(
            f'{os.environ["LS_HOST"]}/api/projects/{project_id}',
            method='patch',
            data=project)
        if patched_project.get('status_code'):
            logger.error(patched_project)
    return
