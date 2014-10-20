import abc
import copy

from mongoengine import ValidationError
import pecan
from pecan import rest
import six
from six.moves import http_client

from st2common.models.base import jsexpose
from st2common import log as logging


LOG = logging.getLogger(__name__)

RESERVED_QUERY_PARAMS = {
    'id': 'id',
    'name': 'name',
    'sort': 'order_by',
    'offset': 'offset',
    'limit': 'limit'
}


@six.add_metaclass(abc.ABCMeta)
class ResourceController(rest.RestController):
    model = abc.abstractproperty
    access = abc.abstractproperty
    supported_filters = abc.abstractproperty
    options = {
        'sort': []
    }

    def __init__(self):
        self.supported_filters = copy.deepcopy(self.__class__.supported_filters)
        self.supported_filters.update(RESERVED_QUERY_PARAMS)

    def _get_all(self, **kwargs):
        sort = kwargs.get('sort').split(',') if kwargs.get('sort') else []
        for i in range(len(sort)):
            sort.pop(i)
            direction = '-' if sort[i].startswith('-') else ''
            sort.insert(i, direction + self.supported_filters[sort[i]])
        kwargs['sort'] = sort if sort else copy.copy(self.options.get('sort'))
        filters = {v: kwargs[k] for k, v in six.iteritems(self.supported_filters) if kwargs.get(k)}
        instances = self.access.query(**filters)
        return [self.model.from_model(instance) for instance in instances]

    @jsexpose()
    def get_all(self, **kwargs):
        return self._get_all(**kwargs)

    @jsexpose(str)
    def get_one(self, id):
        instance = None
        try:
            instance = self.access.get(id=id)
        except ValidationError:
            instance = None  # Someone supplied a mongo non-comformant id.

        if not instance:
            msg = 'Unable to identify resource with id "%s".' % id
            pecan.abort(http_client.NOT_FOUND, msg)
        return self.model.from_model(instance)
