import typing

import requests
import json
import dataclasses
import pprint

USERNAME = 'admin'
PASSWORD = 'password'
PROTOCOL = 'http'
BASE_URL = '192.168.0.121:7990'

headers_base = {
    "Accept": "application/json"
}


@dataclasses.dataclass
class Repository:
    name: str
    description: str
    repository_slug: str
    users: list[str] = dataclasses.field(default_factory=list)
    groups: list[str] = dataclasses.field(default_factory=list)
    validated: bool = False

    def validate(self, rules: typing.Iterable[typing.Callable[[str], bool]]) -> bool:
        # TODO добавить проверку на пустой проект, наличие всех необходимых групп, отсутствие лишних ролей
        pass


@dataclasses.dataclass
class Project:
    name: str
    key: str
    description: str
    groups: list[str] = dataclasses.field(default_factory=list)
    users: list[str] = dataclasses.field(default_factory=list)
    repositories: list[Repository] = dataclasses.field(default_factory=list)
    validated: bool = False

    def validate(self, rules: typing.Iterable[typing.Callable[[str], bool]]) -> bool:
        pass


# Utility methods
def make_request(url, headers, method='GET') -> requests.Response:
    response = requests.request(
        method,
        url,
        headers=headers,
        auth=(USERNAME, PASSWORD)
    )
    return response


def create_rbac_project_rules(project_name: str) -> tuple[str, str, str]:
    return 'rbac_bitbucket_read', f'rbac_bitbucket_{project_name}_admin', f'rbac_bitbucket_{project_name}_write'


def validate_units_rules(units: list[str], rules: tuple) -> bool:
    # TODO Проверка на наличие всех необходимых групп, rules цепочка функторов func(unit: str) -> bool
    for unit in units:
        if unit not in rules:
            return False
    return True


def validate_groups(groups: list[str], rules: tuple) -> bool:
    return validate_units_rules(groups, rules)


def validate_users(users: list[str]) -> bool:
    if not users:
        return True
    return all([user.startswith('srv') for user in users])


# API methods
def get_project_unit(unit: str, project_key: str) -> list[str]:
    if unit not in ('users', 'groups'):
        raise Exception('allowed units are users, groups')
    short_unit = unit[:-1]
    url = f"{PROTOCOL}://{BASE_URL}/rest/api/latest/projects/{project_key}/permissions/{unit}"
    response = make_request(url, headers_base)
    values = response.json().get('values', [])
    project_unit = [value[short_unit]['name'] for value in values]
    return project_unit


def get_repo_unit(unit: str, project_key: str, repository_slug: str) -> list[str]:
    # TODO Избавиться от дублирования
    if unit not in ('users', 'groups'):
        raise Exception('allowed units are users, groups')
    short_unit = unit[:-1]
    url = f"{PROTOCOL}://{BASE_URL}/rest/api/latest/projects/{project_key}/repos/{repository_slug}/permissions/{unit}"
    response = make_request(url, headers_base)

    values = response.json().get('values', [])
    repo_unit = [value[short_unit]['name'] for value in values]
    return repo_unit


def get_repositories(project_key: str) -> list[Repository]:
    url = f"{PROTOCOL}://{BASE_URL}/rest/api/latest/projects/{project_key}/repos"
    response = make_request(url, headers_base)
    repositories = []
    for repository in response.json()['values']:
        description = repository.get('description', '')
        repository_slug = repository['slug']
        users = get_repo_unit('users', project_key, repository_slug)
        groups = get_repo_unit('groups', project_key, repository_slug)
        validated = validate_users(users) & validate_groups(groups, ())
        repositories.append(Repository(
            name=repository['name'],
            description=description,
            repository_slug=repository_slug,
            users=users,
            groups=groups,
            validated=validated,
        ))
    return repositories


def audit() -> list[Project]:
    # TODO Вынести логику запроса проектов
    limit = 30
    url = f"{PROTOCOL}://{BASE_URL}/rest/api/latest/projects?limit={limit}"
    response = make_request(url, headers_base)

    projects = []
    for project in response.json()['values']:
        project_key = project['key']
        groups = get_project_unit('groups', project['key'])
        users = get_project_unit('users', project['key'])
        validated = validate_users(users) & validate_groups(groups, create_rbac_project_rules(project['name']))
        description = project.get('description', '')
        repositories = get_repositories(project_key)
        projects.append(Project(
            name=project['name'],
            key=project_key,
            description=description,
            users=users,
            groups=groups,
            repositories=repositories,
            validated=validated
        ))
    return projects


def main():
    audit_result = audit()
    for result in audit_result:
        pprint.pprint(result)


if __name__ == '__main__':
    main()
