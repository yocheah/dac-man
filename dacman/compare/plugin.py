
from straight.plugin import load
from dacman.compare.base import ComparatorBase
import dacman.core.utils as dacman_utils
import os


class PluginManager(object):
    @classmethod
    def load_comparator(cls, data_type):
        plugin_config = os.path.join(os.getenv('HOME'), '.dacman/config/plugins.yaml')
        if os.path.exists(plugin_config):
            plugin_info = dacman_utils.load_yaml(plugin_config)
            if plugin_info is not None:
                if data_type in plugin_info:
                    if data_type in COMPARATORS_MAP:
                        for comparator in COMPARATORS_MAP[data_type]:
                            if comparator.__class__.__name__ == plugin_info[data_type]:
                                return comparator
                        else:
                            print("Configured plugin {} not found. Using available plugins.".format(plugin_info[data_type]))
                    else:
                        print("Plugin for {} not found. Using default plugin.".format(data_type))
        if data_type in COMPARATORS_MAP:
            return COMPARATORS_MAP[data_type][0]
        else:
            return COMPARATORS_MAP['default'][0]

    @classmethod
    def get_plugins(cls):
        plugins = load("dacman.plugins", subclasses=ComparatorBase)
        plugin_list = []
        for plugin in plugins:
            plugin_list.append(plugin)
        return plugin_list


def _get_comparators():
    plugins = load("dacman.plugins", subclasses=ComparatorBase)
    comparators = {}
    for plugin in plugins:
        comparator = plugin()
        supports = comparator.supports()
        # print("Plugin {} supports: {}".format(plugin.__name__, supports))
        if type(supports) == list:
            for s in supports:
                _add_comparator(s, comparator, comparators)
        else:
            _add_comparator(supports, comparator, comparators)

    return comparators


def _add_comparator(supports, comparator, comparators):
    if supports in comparators:
        comparators[supports].append(comparator)
    else:
        comparators[supports] = [comparator]


COMPARATORS_MAP = _get_comparators()