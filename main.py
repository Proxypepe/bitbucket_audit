import dataclasses
import pprint


import requests


USERNAME = 'admin'
PASSWORD = 'password'
PROTOCOL = 'http'
BASE_URL = '192.168.0.121:7990'

headers_base = {
    "Accept": "application/json"
}


@dataclasses.dataclass
class Repository:
    """Repository entity"""

    name: str
    description: str
    repository_slug: str
    users: list[str] = dataclasses.field(default_factory=list)
    groups: list[str] = dataclasses.field(default_factory=list)
    validated: bool = False
    res_description: str = ''


@dataclasses.dataclass
class Project:
    """Project entity"""

    # pylint: disable=too-many-instance-attributes

    name: str
    key: str
    description: str
    groups: list[str] = dataclasses.field(default_factory=list)
    users: list[str] = dataclasses.field(default_factory=list)
    repositories: list[Repository] = dataclasses.field(default_factory=list)
    validated: bool = False
    result_description: str = ''


# Utility methods
def make_request(url, headers, method='GET', timeout=10) -> requests.Response:
    response = requests.request(
        method,
        url,
        headers=headers,
        timeout=timeout,
        auth=(USERNAME, PASSWORD)
    )
    return response


def create_rbac_project_rules(project_name: str) -> tuple[str, str, str]:
    return 'rbac_bitbucket_reader', \
           f'rbac_bitbucket_{project_name}_admin'.replace(' ', '_').lower(), \
           f'rbac_bitbucket_{project_name}_write'.replace(' ', '_').lower()


def is_contains_rbac_all_groups(groups: list[str], project_name: str) -> tuple[bool, str]:
    rbac_groups = create_rbac_project_rules(project_name)
    not_contains_groups = False
    description = ''
    for rbac_group in rbac_groups:
        if rbac_group not in groups:
            not_contains_groups = True
            description += f'Отсутствует группа: {rbac_group} \n'
    return not not_contains_groups, description


def is_not_contains_extra_groups(groups: list[str], project_name: str) -> tuple[bool, str]:
    rbac_groups = create_rbac_project_rules(project_name)
    extra_group = False
    description = ''
    for group in groups:
        if group not in rbac_groups:
            extra_group = True
            description += f'Лишняя группа: {group} \n'
    return not extra_group, description


def is_not_project_empty(repos_size: int) -> tuple[bool, str]:
    return (False, 'Пустой репозиторий') if repos_size == 0 else (True, '')


def validate_users(users: list[str]) -> tuple[bool, str]:
    users_service_filtered = [user.startswith('srv') for user in users]
    return (True, "") \
        if all(users_service_filtered) \
        else (False, 'есть лишние пользователи')


def validate_all(*results) -> tuple[bool, str]:
    boolean_values = [result[0] for result in results]
    val = all(boolean_values)
    description = [result[1] for result in results]
    return val, ' '.join(description)


# API methods
def get_unit(url, unit: str):
    if unit not in ('users', 'groups'):
        raise ValueError('allowed units are users, groups')
    short_unit = unit[:-1]
    response = make_request(url, headers_base)
    values = response.json().get('values', [])
    project_unit = [value[short_unit]['name'] for value in values]
    return project_unit


def get_project_unit(unit: str, project_key: str) -> list[str]:
    url = f"{PROTOCOL}://{BASE_URL}/rest/api/latest/projects/{project_key}/permissions/{unit}"
    return get_unit(url, unit)


def get_repo_unit(unit: str, project_key: str, repository_slug: str) -> list[str]:
    url = f"{PROTOCOL}://{BASE_URL}/rest/api/latest/projects/{project_key}/repos/{repository_slug}/permissions/{unit}"
    return get_unit(url, unit)


#####
def get_repositories(project_key: str) -> list[Repository]:
    url = f"{PROTOCOL}://{BASE_URL}/rest/api/latest/projects/{project_key}/repos"
    response = make_request(url, headers_base)
    repositories = []
    for repository in response.json()['values']:
        description = repository.get('description', '')
        repository_slug = repository.get('slug')
        users = get_repo_unit('users', project_key, repository_slug)
        groups = get_repo_unit('groups', project_key, repository_slug)

        validated, res_description = validate_all(
            validate_users(users),
            (True, '') if not groups else (False, "Есть лишние группы")
        )
        repositories.append(Repository(
            name=repository['name'],
            description=description,
            repository_slug=repository_slug,
            users=users,
            groups=groups,
            validated=validated,
            res_description=res_description,
        ))
    return repositories


def audit() -> list[Project]:
    limit = 30
    url = f"{PROTOCOL}://{BASE_URL}/rest/api/latest/projects?limit={limit}"
    response = make_request(url, headers_base)

    projects = []
    for project in response.json()['values']:
        project_key = project['key']
        project_name = project['name']
        groups = get_project_unit('groups', project['key'])
        users = get_project_unit('users', project['key'])
        description = project.get('description', '')
        repositories = get_repositories(project_key)

        validated, res_description = validate_all(
            is_not_project_empty(len(repositories)),
            is_not_contains_extra_groups(groups, project_name),
            is_contains_rbac_all_groups(groups, project_name),
            validate_users(users),
        )

        projects.append(Project(
            name=project_name,
            key=project_key,
            description=description,
            users=users,
            groups=groups,
            repositories=repositories,
            validated=validated,
            result_description=res_description
        ))
    return projects


def main():
    audit_result = audit()
    for result in audit_result:
        pprint.pprint(result)


if __name__ == '__main__':
    main()
