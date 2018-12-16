# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import re

from sklearn.base import BaseEstimator
from sklearn.base import TransformerMixin


def field(bug, field):
    if field in bug and bug[field] != '---':
        return bug[field]

    return None


class has_str(object):
    def __call__(self, bug):
        return field(bug, 'cf_has_str')


class has_regression_range(object):
    def __call__(self, bug):
        return field(bug, 'cf_has_regression_range')


class has_crash_signature(object):
    def __call__(self, bug):
        return 'cf_crash_signature' in bug and bug['cf_crash_signature'] != ''


class keywords(object):
    def __init__(self, to_ignore=set()):
        self.to_ignore = to_ignore

    def __call__(self, bug):
        keywords = []
        subkeywords = []
        for keyword in bug['keywords']:
            if keyword in self.to_ignore:
                continue

            keywords.append(keyword)

            if keyword.startswith('sec-'):
                subkeywords.append('sec-')
            elif keyword.startswith('csectype-'):
                subkeywords.append('csectype-')
        return keywords + subkeywords


class severity(object):
    def __call__(self, bug):
        return field(bug, 'severity')


class is_coverity_issue(object):
    def __call__(self, bug):
        return re.search('[CID ?[0-9]+]', bug['summary']) is not None or re.search('[CID ?[0-9]+]', bug['whiteboard']) is not None


class has_url(object):
    def __call__(self, bug):
        return bug['url'] != ''


class has_w3c_url(object):
    def __call__(self, bug):
        return 'w3c' in bug['url']


class has_github_url(object):
    def __call__(self, bug):
        return 'github' in bug['url']


class whiteboard(object):
    def __call__(self, bug):
        ret = []

        # TODO: Add any [XXX:YYY] that appears in the whiteboard as [XXX: only

        for elem in ['memshrink', '[ux]']:
            if elem in bug['whiteboard'].lower():
                ret.append(elem)

        return ret


class patches(object):
    def __call__(self, bug):
        return sum(1 for a in bug['attachments'] if a['is_patch'] or a['content_type'] in ['text/x-review-board-request', 'text/x-phabricator-request'])


class landings(object):
    def __call__(self, bug):
        return sum(1 for c in bug['comments'] if '://hg.mozilla.org/' in c['text'])


class title(object):
    def __call__(self, bug):
        ret = []

        keywords = [
            'implement', 'refactor', 'meta', 'tracker', 'dexpcom',
            'indent', 'ui review', 'support', '[ux]',
            'fail', 'npe', 'except', 'broken', 'crash', 'bug', 'differential testing', 'error',
            'addresssanitizer', 'hang ', ' hang', 'jsbugmon', 'leak', 'permaorange', 'random orange',
            'intermittent', 'regression', 'test fix', 'heap overflow', 'uaf', 'use-after-free',
            'asan', 'address sanitizer', 'rooting hazard', 'race condition', 'xss', '[static analysis]',
            'warning c',
        ]
        for keyword in keywords:
            if keyword in bug['summary'].lower():
                ret.append(keyword)

        keyword_couples = [
            ('add', 'test')
        ]
        for keyword1, keyword2 in keyword_couples:
            if keyword1 in bug['summary'].lower() and keyword2 in bug['summary'].lower():
                ret.append(keyword1 + '^' + keyword2)

        return ret


class comments(object):
    def __call__(self, bug):
        ret = set()

        keywords = [
            'refactor',
            'steps to reproduce', 'crash', 'assertion', 'failure', 'leak', 'stack trace', 'regression',
            'test fix', ' hang', 'hang ', 'heap overflow', 'str:', 'use-after-free', 'asan',
            'address sanitizer', 'permafail', 'intermittent', 'race condition', 'unexpected fail',
            'unexpected-fail', 'unexpected pass', 'unexpected-pass', 'repro steps:', 'to reproduce:',
        ]

        casesensitive_keywords = [
            'FAIL', 'UAF',
        ]

        for keyword in keywords:
            if keyword in bug['comments'][0]['text'].lower():
                ret.add('first^' + keyword)

        for keyword in casesensitive_keywords:
            if keyword in bug['comments'][0]['text']:
                ret.add('first^' + keyword)

        mozregression_patterns = [
            'mozregression', 'Looks like the following bug has the changes which introduced the regression', 'First bad revision',
        ]

        for keyword in mozregression_patterns:
            for comment in bug['comments']:
                if keyword in comment['text'].lower():
                    ret.add('mozregression')

        safemode_patterns = [
            'safemode', 'safe mode'
        ]

        for keyword in safemode_patterns:
            for comment in bug['comments']:
                if keyword in comment['text'].lower():
                    ret.add('safemode')

        return list(ret)


class product(object):
    def __call__(self, bug):
        return bug['product']


class component(object):
    def __call__(self, bug):
        return bug['component']


def cleanup_url(text):
    return re.sub(r'http\S+', 'URL', text)


class BugExtractor(BaseEstimator, TransformerMixin):
    def __init__(self, feature_extractors, commit_messages_map=None):
        self.feature_extractors = feature_extractors
        self.commit_messages_map = commit_messages_map
        self.cleanup_functions = [cleanup_url]

    def fit(self, x, y=None):
        return self

    def transform(self, bugs):
        results = []

        for bug in bugs:
            bug_id = bug['id']

            data = {}

            for f in self.feature_extractors:
                res = f(bug)

                if res is None:
                    continue

                if isinstance(res, list):
                    for item in res:
                        data[f.__class__.__name__ + '-' + item] = 'True'
                    continue

                if isinstance(res, bool):
                    res = str(res)

                data[f.__class__.__name__] = res

            # TODO: Try simply using all possible fields instead of extracting features manually.

            for cleanup_function in self.cleanup_functions:
                bug['summary'] = cleanup_function(bug['summary'])
                for c in bug['comments']:
                    c['text'] = cleanup_function(c['text'])

            result = {
                'data': data,
                'title': bug['summary'],
                'comments': ' '.join([c['text'] for c in bug['comments']]),
            }

            if self.commit_messages_map is not None:
                result['commits'] = self.commit_messages_map[bug_id] if bug_id in self.commit_messages_map else ''

            results.append(result)

        return results
