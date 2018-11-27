"""
To hook all the different changes to our api!
"""
from eve.methods.patch import patch_internal
from eve.methods.get import get_internal
from datetime import datetime
from operator import itemgetter

# import dateutil.parser


RESOURCE_PERSONS_PROCESS = 'persons_process'


def _get_end_of_year():
    return datetime(datetime.utcnow().year, 12, 31, 23, 59, 59, 999999)


def _get_end_of_january():
    """End of jan next year"""
    return datetime(datetime.utcnow().year + 1, 1, 31, 23, 59, 59, 999999)


def _get_person(person_id) -> dict:
    """Get person from persons internal

    :param person_id: Person id
    :type person_id: int
    :return org: Returns the person given
    :rtype: dict
    """
    person, _, _, status, _ = get_internal('persons', **{'id': person_id})

    if status == 200:
        if '_items' in person and len(person['_items']) == 1:
            return person['_items'][0]

    return {}


def _compare_list_of_dicts(l1, l2, dict_id='id') -> bool:
    """Sorts lists then compares on the given id in the dicts
    :param l1: list of dicts
    :type l1: list(dict)
    :param l2: list of dicts
    :type l2: list(dict)
    :param dict_id: The id for the dicts
    :type dict_id: any
    :return: True if difference, False if not or can't decide
    """
    try:
        list_1, list_2 = [sorted(l, key=itemgetter(dict_id)) for l in (l1, l2)]
        pairs = zip(list_1, list_2)
        if any(x != y for x, y in pairs):
            return True
        else:
            return False  # They are equal
    except:
        return True  # We do not know if difference


def _get_org(org_id) -> dict:
    """Get org from organizations internal

    :param org_id: Organization id
    :type org_id: int
    :return org: Returns the organization
    :rtype: dict
    """

    org, _, _, status, _ = get_internal('organizations', **{'id': org_id})

    if status == 200:
        if '_items' in org and len(org['_items']) == 1:
            return org['_items'][0]

    return {}


def _get_functions_types(type_id) -> dict:
    """Get org from organizations internal

    :param org_id: Organization id
    :type org_id: int
    :return org: Returns the organization
    :rtype: dict
    """

    function_type, _, _, status, _ = get_internal('functions_types', **{'id': type_id})

    if status == 200:
        if '_items' in function_type and len(function_type['_items']) == 1:
            return function_type['_items'][0]

    return {}


def on_function_post(items) -> None:
    """On every function change, let's update person's functions.

    Function of type ``10000000`` is club membership and this implicates both clubs and activities

    Other function types are updated in a list

    :param items: the function object to be inserted or replaced

    @TODO can "has_paid_membership": false | true be of use?
    """

    for response in items:
        on_function_put(response)


def on_function_put(response) -> None:
    """
    :param response: database object
    :return: None
    """
    person = _get_person(response['person_id'])

    if '_id' in person:

        # Club member! has_paid_membership?
        clubs = person.get('clubs', [])
        activities = person.get('activities', [])

        # Expiry date
        expiry = response.get('to_date', None)

        if response.get('type_id', 0) == 10000000:

            # Set expiry to end year
            if expiry is None:
                expiry = _get_end_of_january()

            # If not deleted and is valid expiry add to club list
            if not response['is_deleted'] and not response['is_passive'] and \
                            expiry is not None and expiry > datetime.utcnow():

                clubs.append(response.get('active_in_org_id'))
            else:
                try:
                    clubs.remove(response.get('active_in_org_id'))
                except ValueError:
                    pass
                except:
                    pass

            # Unique list
            clubs = list(set(clubs))
            # Valid expiry?
            # clubs[:] = [d for d in clubs if d.get('expiry') >= datetime.utcnow()]


            # Activities
            # Do not know which club is actually which activity
            # Need to redo all.
            for club_id in clubs:
                try:
                    org = _get_org(club_id)
                    # Gets the id of main activity
                    # If None, go for 27 (Luftsport/370)
                    # @TODO see if should be None to pass next
                    activity = org.get('main_activity', {}).get('id', 27)
                    if activity is not None:
                        # @TODO see if code should be integer? String now.
                        # activity['code'] = int(activity.get('code', 0))
                        activities.append(activity)
                except:
                    pass

            # Unique list of activities
            activities = list(set(activities))

            # List of dicts
            # activities = list({v['id']: v for v in activities}.values())
            # Valid expiry?
            # activities[:] = [d for d in activities if d.get('expiry') >= datetime.utcnow()]

        # The rest of the functions
        # Considers expiry date, if None then still valid
        f = person.get('functions', [])
        if expiry is None or expiry > datetime.utcnow():
            f.append(response['id'])
        else:
            try:
                f.remove(response.get('id'))
            except:
                pass

        f = list(set(f))
        # Valid expiry?
        # f[:] = [d for d in f if d.get('expiry') >= datetime.utcnow()]

        lookup = {'_id': person['_id']}

        # Update person with new values
        # response, last_modified, etag, status =
        patch_internal(RESOURCE_PERSONS_PROCESS,
                       {'functions': f, 'activities': activities, 'clubs': clubs},
                       False, True, **lookup)

    # Always check and get type name
    # Update the function
    if response.get('type_name', None) is None:
        function_type = _get_functions_types(response.get('type_id', 0))
        if len(function_type) > 0:
            type_name = function_type.get('name', None)
            if type_name is not None:
                patch_internal('functions', {'type_name': type_name}, False, True, **{'_id': response.get('_id')})


def on_license_post(items):
    """pass"""

    for response in items:
        on_license_put(response)


def on_license_put(response):
    """pass"""

    expiry = response.get('period_to_date', None)  # dateutil.parser.parse(response.get('period_to_date', None))

    # Set expiry to end year
    if expiry is None:
        expiry = _get_end_of_year()

    # Always get person
    person = _get_person(response['person_id'])
    if '_id' in person:

        licenses = person.get('licenses', [])

        # If valid expiry
        if expiry is None or expiry >= datetime.utcnow():

            try:
                licenses.append({'id': response.get('id'),
                                 'status_id': response.get('status_id', 0),
                                 'status_date': response.get('status_date', None),
                                 'expiry': response.get('period_to_date', None),
                                 'type_id': response.get('type_id', None),
                                 'type_name': response.get('type_name', None)})

            except:
                pass

        # Unique
        licenses = list({v['id']: v for v in licenses}.values())

        # Valid expiry
        licenses[:] = [d for d in licenses if d.get('expiry') >= datetime.utcnow()]

        # Patch if difference
        if '_id' in person and _compare_list_of_dicts(licenses, person.get('licenses', [])) is True:
            lookup = {'_id': person['_id']}
            patch_internal(RESOURCE_PERSONS_PROCESS, {'licenses': licenses}, False, True, **lookup)


def on_competence_post(items):
    """Competence fields:

    passed bool
    valid_until datetime

    """
    for response in items:
        on_competence_put(response)


def on_competence_put(response):
    """"""

    expiry = response.get('valid_until', None)

    # Set expiry to end year
    if expiry is None:
        expiry = _get_end_of_year()

    person = _get_person(response['person_id'])

    if '_id' in person:

        competence = person.get('competences', [])

        # Add this competence?
        if expiry is not None and isinstance(expiry, datetime) and expiry >= datetime.utcnow():

            try:
                competence.append({'id': response.get('id'),
                                   '_code': response.get('_code', None),
                                   'issuer': response.get('approved_by_person_id', None),
                                   'expiry': response.get('valid_until', None),
                                   'paid': response.get('paid_date', None)})
            except:
                pass

        # Always remove stale competences
        competence[:] = [d for d in competence if d.get('expiry') >= datetime.utcnow()]

        # Always unique by id
        competence = list({v['id']: v for v in competence}.values())

        # Patch if difference
        if _compare_list_of_dicts(competence, person.get('competence', [])) is True:
            lookup = {'_id': person['_id']}
            patch_internal(RESOURCE_PERSONS_PROCESS, {'competences': competence}, False, True, **lookup)


def on_person_after_post(items):
    for response in items:
        _update_person(response)


def on_person_after_put(item, original=None):
    _update_person(item)


def _update_person(item):
    lookup = {'person_id': item['id']}

    competences, _, _, c_status, _ = get_internal('competences', **lookup)
    if c_status == 200:
        on_competence_post(competences.get('_items', []))

    licenses, _, _, l_status, _ = get_internal('licenses', **lookup)
    if l_status == 200:
        on_license_post(licenses.get('_items', []))

    functions, _, _, f_status, _ = get_internal('functions', **lookup)
    if f_status == 200:
        on_function_post(functions.get('_items', []))
