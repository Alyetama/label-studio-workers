#!/usr/bin/env python
# coding: utf-8

import os
import random

import matplotlib
from loguru import logger

from utils import api_request


def add_new_project(new_project_folder_name):
    all_projects = api_request(
        f'{os.environ["LS_HOST"]}/api/projects')['results']
    existing_titles = [p['title'] for p in all_projects]
    if new_project_folder_name in existing_titles:
        logger.debug(
            f'`{new_project_folder_name}` already exists! Skipping...')
        return

    logger.debug(f'Creating new project: `{new_project_folder_name}`')

    template_id = all_projects[0]['id']
    template = api_request(
        f'{os.environ["LS_HOST"]}/api/projects/{template_id}')

    for k in [
            'model_version', 'created_by', 'created_at', 'task_number',
            'useful_annotation_number', 'ground_truth_number',
            'skipped_annotations_number', 'total_annotations_number',
            'total_predictions_number', 'overlap_cohort_percentage'
    ]:
        template.pop(k)

    color = random.choice(
        [x for x in list(matplotlib.colors.cnames.values()) if x != '#FFFFFF'])
    template.update({'title': new_project_folder_name, 'color': color})

    url = f'{os.environ["LS_HOST"]}/api/projects'
    new_project = api_request(url, method='post', data=template)
    logger.debug(new_project)
    return new_project


def add_and_sync_data_storage(project_id,
                              project_name,
                              s3_endpoint_scheme='https://') -> dict:
    storage_dict = {
        "type": "s3",
        "presign": True,
        "title": project_name,
        "bucket": "data",
        "prefix": project_name,
        "use_blob_urls": True,
        "aws_access_key_id": os.environ['S3_ACCESS_KEY'],
        "aws_secret_access_key": os.environ['S3_SECRET_KEY'],
        "region_name": 'us-east-1',
        "s3_endpoint": f'{s3_endpoint_scheme}{os.environ["S3_ENDPOINT"]}',
        "recursive_scan": True,
        "project": project_id
    }
    storage_request = {
        'url': f'{os.environ["LS_HOST"]}/api/storages/s3',
        'method': 'post',
        'data': storage_dict
    }
    logger.debug(f'Request: {storage_request}')

    storage_response = api_request(**storage_request)
    logger.debug(f'Response: {storage_response}')
    storage_id = storage_response['id']

    sync_request = {
        'url': f'{os.environ["LS_HOST"]}/api/storages/s3/{storage_id}/sync',
        'method': 'post',
        'data': {
            'project': project_id
        }
    }
    logger.debug(f'Request: {sync_request}')
    logger.debug('Running sync...')
    sync_response = api_request(**sync_request, return_text=True)

    logger.debug(f'Response: {sync_response}')
    return sync_response
