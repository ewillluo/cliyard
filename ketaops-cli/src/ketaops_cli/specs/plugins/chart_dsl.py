"""Chart YAML ↔ Pithos XML conversion.

Port of :file:`ketacli/sdk/chart/dsl.py` conversion logic, stripped of
ketacli-specific hook integrations.  Provides the two core conversion
functions and all supporting builder classes.
"""

import json
import re
import uuid
import xml.etree.ElementTree as ET
from html import unescape as html_unescape
from xml.dom import minidom
from xml.sax.saxutils import escape as xml_escape

import yaml

_e = xml_escape


def _parse_json(text):
    """Parse JSON from XML text content, handling HTML-escaped quotes."""
    return json.loads(html_unescape(text))


# =============================================================================
# String-based XML helpers
# =============================================================================


def _snake_to_kebab(name):
    return name.replace('_', '-')


def _dict_to_xml_elements(data, indent=6):
    lines = []
    pad = ' ' * indent
    for key, value in data.items():
        tag = _snake_to_kebab(key)
        if isinstance(value, dict):
            inner = _dict_to_xml_elements(value, indent + 2)
            if inner:
                lines.append(f'{pad}<{tag}>')
                lines.append(inner)
                lines.append(f'{pad}</{tag}>')
            else:
                lines.append(f'{pad}<{tag} />')
        elif isinstance(value, list):
            json_val = json.dumps(value)
            lines.append(f'{pad}<{tag}>{json_val}</{tag}>')
        elif isinstance(value, bool):
            lines.append(f'{pad}<{tag}>{str(value).lower()}</{tag}>')
        elif value is None:
            lines.append(f'{pad}<{tag} />')
        else:
            lines.append(f'{pad}<{tag}>{value}</{tag}>')
    return '\n'.join(lines)


def _build_metric_config(chart):
    metric = chart.get('metric', {})
    if not metric.get('key'):
        return None
    cfg = {
        "metrics": [{
            "key": metric.get("key", ""),
            "name": chart.get("name", "Chart"),
            "aggregation": metric.get("aggregation", "avg"),
            "unit": metric.get("unit", "none"),
            "groupBy": metric.get("groupBy", []),
            "fns": [],
            "display": True,
            "index": "a",
            "aliaseName": "",
            "aggregationConfig": "",
            "filters": [],
        }],
        "timeSpan": metric.get("timeSpan", "1m"),
    }
    if metric.get("sort"):
        cfg["metrics"][0]["fns"] = [{
            "type": "sort",
            "config": {
                "type": metric["sort"].get("by", "avg"),
                "reverse": metric["sort"].get("reverse", "false"),
                "N": metric["sort"].get("count", 10),
            }
        }]
    return json.dumps(cfg)


# =============================================================================
# XMLBuilder
# =============================================================================


class XMLBuilder:
    """Fluent XML builder on top of ElementTree."""

    def __init__(self, root_tag, **attrs):
        self.root = ET.Element(root_tag, **attrs)
        self._cdata_count = 0
        self._cdata_map = {}

    def add(self, tag, text=None, **attrs):
        """Add a child element to root."""
        elem = ET.SubElement(self.root, tag, attrs)
        if text is not None:
            elem.text = str(text)
        return elem

    def add_cdata(self, tag, cdata_text):
        """Add a child element whose text content will be wrapped in CDATA."""
        elem = ET.SubElement(self.root, tag)
        idx = self._cdata_count
        self._cdata_count += 1
        placeholder = f'__KETACLI_CDATA_{idx}__'
        elem.text = placeholder
        self._cdata_map[placeholder] = cdata_text
        return elem

    def to_string(self):
        """Serialize to compact XML string (with CDATA sections resolved)."""
        xml_str = ET.tostring(self.root, encoding='unicode')
        for placeholder, cdata_text in self._cdata_map.items():
            xml_str = xml_str.replace(placeholder, f'<![CDATA[{cdata_text}]]>')
        return xml_str

    @staticmethod
    def indent_xml(xml_str):
        """Pretty-print XML with 2-space indent."""
        try:
            dom = minidom.parseString(xml_str)
            result = dom.toprettyxml(indent='  ')
            lines = result.split('\n')
            if lines and lines[0].startswith('<?xml'):
                lines = lines[1:]
            return '\n'.join(lines).rstrip('\n')
        except Exception:
            return xml_str


# =============================================================================
# _dict_to_et
# =============================================================================


def _dict_to_et(parent, data):
    """Add child elements to *parent* for each key-value in *data* dict.

    Same semantics as _dict_to_xml_elements but builds an ElementTree instead
    of producing a string.
    """
    for key, value in data.items():
        tag = _snake_to_kebab(key)
        if isinstance(value, dict):
            child = ET.SubElement(parent, tag)
            _dict_to_et(child, value)
        elif isinstance(value, list):
            elem = ET.SubElement(parent, tag)
            elem.text = json.dumps(value)
        elif isinstance(value, bool):
            elem = ET.SubElement(parent, tag)
            elem.text = str(value).lower()
        elif value is None:
            ET.SubElement(parent, tag)
        else:
            elem = ET.SubElement(parent, tag)
            elem.text = str(value)


# =============================================================================
# Chart Builder hierarchy
# =============================================================================


class ChartBuilder:
    """Base chart builder. Subclasses override build methods.

    Each subclass declares a ``chart_types`` set. The registry (BUILDERS dict)
    maps each type string to a singleton instance of the matching builder.
    """

    chart_types: set = set()

    def build(self, chart, chart_id):
        """Build a ``<v-chart>`` XML string for the given chart dict."""
        b = XMLBuilder('v-chart')
        chart_type = chart.get('type', 'area')
        b.root.set('type', chart_type)

        self._build_header(b, chart, chart_id)
        self._build_search(b, chart)
        b.add('description')
        self._build_body(b, chart)

        xml_str = b.to_string()
        return XMLBuilder.indent_xml(xml_str)

    def _build_header(self, b, chart, chart_id):
        b.add('id', chart_id)

    def _build_search(self, b, chart):
        pass

    def _build_body(self, b, chart):
        pass


# ---------------------------------------------------------------------------
# Standard chart  (area, line, bar, vertical-bar, stack-*, line-bar-y2)
# ---------------------------------------------------------------------------


class StandardChartBuilder(ChartBuilder):
    """Builder for standard metric/log charts with axis, legend, options."""

    chart_types = {
        'area', 'line', 'bar', 'vertical-bar',
        'stack-bar', 'stack-area', 'stack-vertical-bar',
        'line-bar-y2',
    }

    def _build_header(self, b, chart, chart_id):
        name = chart.get('name', 'Chart')
        mode = chart.get('mode', 'metric')
        configs = chart.get('configs', {})
        flag = 'metric' if mode == 'metric' else 'log'
        hide_header = 'true' if chart.get('hide_header', False) else 'false'

        b.add('id', chart_id)
        title = b.add('title')
        ET.SubElement(title, 'name').text = name
        b.add('flag', flag)
        b.add('hide-header', hide_header)
        b.add('hide-custom-time', 'false')

    def _build_search(self, b, chart):
        mode = chart.get('mode', 'metric')
        query = chart.get('query', '')
        search = b.add('search')

        if mode == 'metric':
            mc = _build_metric_config(chart)
            if mc:
                ET.SubElement(search, 'query').text = '| makeresults'
                ET.SubElement(search, 'metric-config').text = mc
                ET.SubElement(search, 'format').text = 'TABLE_FULL_JOIN'
        elif mode == 'log' and query:
            ET.SubElement(search, 'query').text = query
            ET.SubElement(search, 'format').text = 'TABLE_FULL_JOIN'

    def _build_body(self, b, chart):
        configs = chart.get('configs', {})

        legend_config = configs.get(
            'legend', {'position': 'top', 'metrics': ['avg', 'max']},
        )
        legend_elem = b.add('legend')
        _dict_to_et(legend_elem, legend_config)

        groups = configs.get('groups', [])
        b.add('groups', json.dumps(groups))

        default_x_axis = {
            'field': '_time', 'type': 'category', 'label_rotation': 0,
            'label_show_mode': 'showauto', 'hide_name': 'false',
            'unit': ['none', 'short'], 'precision': 2,
            'min_mode': 'auto', 'max_mode': 'auto', 'interval_type': 'auto',
        }
        x_axis_config = {**default_x_axis, **configs.get('x_axis', {})}
        x_axis_elem = b.add('x-axis')
        _dict_to_et(x_axis_elem, x_axis_config)

        default_y_axis = {
            'scale': 'value', 'unit': ['none', 'none'], 'precision': 2,
            'min_mode': 'auto', 'max_mode': 'auto', 'interval_type': 'auto',
            'y_empty_value_mode': 'line',
            'line_data_config': {
                'smooth_line': 'false', 'mark_point_type': 'hide',
                'point': {'type': 'none'},
            },
        }
        y_axis_config = {**default_y_axis, **configs.get('y_axis', {})}
        y_fields = y_axis_config.pop('fields', [])

        y_axis_elem = b.add('y-axis')
        ET.SubElement(y_axis_elem, 'fields').text = json.dumps(y_fields)
        ET.SubElement(y_axis_elem, 'sub-fields').text = '[]'
        ET.SubElement(y_axis_elem, 'name')
        ET.SubElement(y_axis_elem, 'hide-name').text = 'false'
        _dict_to_et(y_axis_elem, y_axis_config)
        b.add_cdata(
            'fields-getter',
            'const result = []; const fields = $fields$;'
            ' for(let i = 0; i < fields.length; i++)'
            ' { if(fields[i].type === "metric") { result.push(fields[i].name); } }'
            ' return result',
        )
        ET.SubElement(y_axis_elem, 'display-fields').text = '[]'

        b.add('option', 'classical', name='style.colorMode')
        b.add('option', 'legend', name='style.tooltipType')
        b.add('option', 'false', name='style.showToolBox')
        b.add('option', 'hide', name='style.markPointType')
        b.add('option', 'false', name='style.smoothLine')

        point_elem = b.add('point')
        ET.SubElement(point_elem, 'type').text = 'none'
        ET.SubElement(point_elem, 'size')
        ET.SubElement(point_elem, 'border-color')
        ET.SubElement(point_elem, 'border-width')


# ---------------------------------------------------------------------------
# Single-value chart
# ---------------------------------------------------------------------------


class SimpleChartBuilder(ChartBuilder):
    """Builder for single-value (KPI) charts."""

    chart_types = {'single-value'}

    def _build_header(self, b, chart, chart_id):
        name = chart.get('name', 'Chart')
        query = chart.get('query', '')

        b.root.set('style', 'height: 0; flex: 1 1 0px;')
        b.add('id', chart_id)
        title = b.add('title')
        ET.SubElement(title, 'name').text = name
        ET.SubElement(title, 'color')
        hide_header = 'true' if chart.get('hide_header', False) else 'false'
        b.add('hide-header', hide_header)
        b.add('hide-drill-down', 'true')
        b.add('hide-custom-time', 'false')
        if not query and _build_metric_config(chart):
            b.add('flag', 'metric')

    def _build_search(self, b, chart):
        query = chart.get('query', '')
        search = b.add('search')

        if query:
            ET.SubElement(search, 'query').text = query
        else:
            mc = _build_metric_config(chart)
            if mc:
                ET.SubElement(search, 'metric-config').text = mc
                ET.SubElement(search, 'format').text = 'TABLE_FULL_JOIN'

        ET.SubElement(search, 'collect-size').text = '-1'
        ET.SubElement(search, 'limit').text = '10'

    def _build_body(self, b, chart):
        configs = chart.get('configs', {})

        data_font = configs.get('data_font', {'font_size': 50})
        data_font_elem = b.add('data-font')
        _dict_to_et(data_font_elem, data_font)

        drilldown = b.add('drilldown')
        link = ET.SubElement(drilldown, 'link')
        ET.SubElement(link, 'none')

        color_splitter = configs.get('color_splitter', {})
        cs_elem = b.add('color-splitter')
        ET.SubElement(cs_elem, 'scale').text = json.dumps(
            color_splitter.get('scale', ['', '']),
        )
        palette = color_splitter.get('color_palette', ['#33C8EF'])
        ET.SubElement(cs_elem, 'color-palette', {'type': 'list'}).text = (
            json.dumps(palette)
        )

        b.add('gauge-min', '0')
        b.add('gauge-max', '0')

        color_elem = b.add('color')
        ET.SubElement(color_elem, 'numeric').text = 'true'
        sv_metrics = configs.get('style', {}).get(
            'metrics', configs.get('y_axis', {}).get('fields', []),
        )
        ET.SubElement(color_elem, 'metrics').text = json.dumps(sv_metrics)

        display_field = configs.get('display_field', {})
        df_elem = b.add('display-field')
        ET.SubElement(df_elem, 'position').text = str(
            display_field.get('position', 'right'),
        )
        ET.SubElement(df_elem, 'font-size').text = str(
            display_field.get('font_size', 12),
        )

        sv_style = configs.get('style', {})
        sv_metrics = sv_style.get(
            'metrics', configs.get('y_axis', {}).get('fields', []),
        )
        sv_groups = sv_style.get('groups', ['_time'])

        b.add('option', json.dumps(['none', 'short']), name='style.unit')
        b.add('option', '2', name='style.precision')
        b.add('option', json.dumps(sv_metrics), name='style.metrics')
        b.add('option', json.dumps(sv_groups), name='style.groups')

        b.add('option', 'empty', name='style.nullValueMode')
        b.add('option', 'value', name='style.colorMode')
        b.add('option', 'none', name='style.trendMode')


# ---------------------------------------------------------------------------
# Pie / Ring chart
# ---------------------------------------------------------------------------


class PieChartBuilder(ChartBuilder):
    """Builder for pie-bucket and pie-ring-bucket charts."""

    chart_types = {'pie-bucket', 'pie-ring-bucket'}

    def _build_header(self, b, chart, chart_id):
        name = chart.get('name', 'Chart')
        query = chart.get('query', '')

        b.root.set('style', 'height: 0; flex: 1 1 0px;')
        b.add('id', chart_id)
        title = b.add('title')
        ET.SubElement(title, 'name').text = name
        ET.SubElement(title, 'color')
        hide_header = 'true' if chart.get('hide_header', False) else 'false'
        b.add('hide-header', hide_header)
        b.add('hide-drill-down', 'true')
        b.add('hide-custom-time', 'false')
        if not query and _build_metric_config(chart):
            b.add('flag', 'metric')

    def _build_search(self, b, chart):
        query = chart.get('query', '')
        search = b.add('search')

        if query:
            ET.SubElement(search, 'query').text = query
        else:
            mc = _build_metric_config(chart)
            if mc:
                ET.SubElement(search, 'metric-config').text = mc
                ET.SubElement(search, 'format').text = 'TABLE_FULL_JOIN'

        ET.SubElement(search, 'collect-size').text = '-1'
        ET.SubElement(search, 'limit').text = '10'

    def _build_body(self, b, chart):
        configs = chart.get('configs', {})

        sv_style = configs.get('style', {})
        sv_metrics = sv_style.get(
            'metrics', configs.get('y_axis', {}).get('fields', []),
        )
        sv_groups = sv_style.get('groups', ['_time'])

        b.add('option', json.dumps(['none', 'short']), name='style.unit')
        b.add('option', '2', name='style.precision')
        b.add('option', json.dumps(sv_metrics), name='style.metrics')
        b.add('option', json.dumps(sv_groups), name='style.groups')

        b.add('option', 'classical', name='style.colorMode')
        b.add('option', 'false', name='style.showTitleBucket')
        b.add('option', 'hide', name='style.dataFormat')
        b.add('option', '30', name='style.circularWidth')
        b.add('option', 'false', name='style.play')
        b.add('option', '[20]', name='style.maxSlices')
        b.add('option', '[]', name='style.labelTypes')


# ---------------------------------------------------------------------------
# Grid-table chart
# ---------------------------------------------------------------------------


class GridTableBuilder(ChartBuilder):
    """Builder for grid-table charts."""

    chart_types = {'grid-table'}

    def _build_header(self, b, chart, chart_id):
        name = chart.get('name', 'Chart')
        query = chart.get('query', '')

        b.root.set('style', 'height: 0; flex: 1 1 0px;')
        b.add('id', chart_id)
        title = b.add('title')
        ET.SubElement(title, 'name').text = name
        ET.SubElement(title, 'color')
        hide_header = 'true' if chart.get('hide_header', False) else 'false'
        b.add('hide-header', hide_header)
        b.add('hide-drill-down', 'true')
        b.add('hide-custom-time', 'false')
        if not query and _build_metric_config(chart):
            b.add('flag', 'metric')

    def _build_search(self, b, chart):
        query = chart.get('query', '')
        search = b.add('search')

        if query:
            ET.SubElement(search, 'query').text = query
        else:
            mc = _build_metric_config(chart)
            if mc:
                ET.SubElement(search, 'metric-config').text = mc
                ET.SubElement(search, 'format').text = 'TABLE_FULL_JOIN'

        ET.SubElement(search, 'collect-size').text = '-1'
        ET.SubElement(search, 'limit').text = '10'

    def _build_body(self, b, chart):
        pass


# =============================================================================
# Builder registry
# =============================================================================

BUILDERS = {}
for _cls in (StandardChartBuilder, SimpleChartBuilder, PieChartBuilder,
             GridTableBuilder):
    for _t in _cls.chart_types:
        BUILDERS[_t] = _cls()


def get_builder(chart_type):
    """Return a ChartBuilder instance for *chart_type*.

    Falls back to ``StandardChartBuilder`` for unknown types.
    """
    return BUILDERS.get(chart_type, BUILDERS['area'])


# =============================================================================
# _build_chart_xml
# =============================================================================


def _build_chart_xml(chart):
    chart_type = chart.get('type', 'area')
    pos = chart.get('pos', {})
    chart_id = str(uuid.uuid4())

    x = int(pos.get('x', 0))
    y = int(pos.get('y', 0))
    w = int(pos.get('w', 12))
    h = int(pos.get('h', 6))

    builder = get_builder(chart_type)
    vchart_xml = builder.build(chart, chart_id).strip()

    if not vchart_xml:
        return ''

    indented = '\n'.join(
        f'        {line}' if line.strip() else line
        for line in vchart_xml.split('\n')
    )

    return (
        f'      <v-layout layout-id="layoutC_{chart_id}"'
        f' top="{y}" left="{x}" width="{w}" height="{h}">\n'
        f'{indented}\n'
        f'      </v-layout>'
    )


# =============================================================================
# chart_yaml_to_pithos — YAML → Pithos XML
# =============================================================================


def chart_yaml_to_pithos(yaml_path):
    """Convert a chart DSL YAML file to Pithos XML.

    Returns:
        ``(xml_content: str, xml_vars_json: str)`` tuple.
    """
    with open(yaml_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    if isinstance(config, list):
        config = config[0] if config else {}

    title = config.get('title', config.get('name', 'Dashboard'))
    dashboard_cfg = config.get('dashboard', {})
    charts = config.get('charts', [])
    variables = config.get('variables', {})

    refresh_interval = dashboard_cfg.get('refresh_interval', 's30')
    time_cfg = dashboard_cfg.get('time', {'earliest': 'm15'})
    layout_options = dashboard_cfg.get(
        'layout_options', {'gapX': 16, 'gapY': 16, 'cols': 12, 'rowHeight': 40},
    )

    # Build xmlVariables JSON
    xml_vars = {
        "operationBarToken": {
            "value": {
                "refreshInterval": refresh_interval,
                "time": time_cfg,
                "hideOnFullscreen": dashboard_cfg.get('hide_on_fullscreen', False),
                "scaleOnFullscreen": dashboard_cfg.get('scale_on_fullscreen', [0, 0]),
                "layoutOptions": layout_options,
            },
            "type": "normal",
        },
    }

    # Add user-defined variables
    for var_name, var_config in variables.items():
        v = {
            'type': var_config.get('type', 'normal'),
            'value': var_config.get('value', ''),
        }
        xml_vars[var_name] = v
    if 'interval' not in xml_vars:
        xml_vars['interval'] = {'value': '1m', 'type': 'normal'}

    # Build variable inputs XML
    var_rows = []
    if variables:
        var_rows = []
        for var_name, var_config in variables.items():
            inp = var_config.get('input', {})
            if not inp:
                continue
            inp_type = inp.get('type', 'text')
            label = inp.get('label', var_name)
            parts = [
                f'            <v-input type="{inp_type}"'
                f' mode="vertical" token="{var_name}">',
            ]
            parts.append(f'              <label>{label}</label>')
            search = inp.get('search', {})
            if search.get('query'):
                parts.append(f'              <search>')
                parts.append(f'                <query>{search["query"]}</query>')
                parts.append(f'                <earliest />')
                parts.append(f'                <latest />')
                parts.append(f'              </search>')
            for key in (
                'field_for_label', 'field_for_value', 'auto_refresh',
                'select_all', 'value_prefix', 'value_suffix',
                'delimiter', 'multi_mode',
            ):
                val = inp.get(key)
                if val is not None:
                    parts.append(
                        f'              <{_snake_to_kebab(key)}>{val}'
                        f'</{_snake_to_kebab(key)}>',
                    )
            if 'initial_value' in inp:
                iv = inp['initial_value']
                if isinstance(iv, list):
                    iv = json.dumps(iv)
                parts.append(f'              <initial-value>{iv}</initial-value>')
            if inp_type == 'dropdown' and inp.get('choices'):
                for cv, cl in inp['choices'].items():
                    parts.append(
                        f'              <choice value="{cv}">{cl}</choice>',
                    )
            parts.append(f'            </v-input>')
            var_rows.append('\n'.join(parts))

    # Build chart XML
    chart_xml = '\n'.join(_build_chart_xml(c) for c in charts)

    # Build full dashboard XML
    earliest = time_cfg.get('earliest', 'm15')
    latest = time_cfg.get('latest', '')
    latest_xml = f'\n            <latest>{latest}</latest>' if latest else ''
    hide_fs = str(dashboard_cfg.get('hide_on_fullscreen', False)).lower()
    scale = json.dumps(dashboard_cfg.get('scale_on_fullscreen', [0, 0]))

    var_section = ''
    if var_rows:
        row_id = str(uuid.uuid4())
        cols_xml = '\n'.join(
            f'          <v-col col-id="{str(uuid.uuid4())}" span="12">\n{x}\n          </v-col>'
            for x in var_rows
        )
        var_section = (
            f'      <variables fold="true">\n'
            f'        <v-row row-id="{row_id}" type="flex" gutter="16">\n'
            f'{cols_xml}\n'
            f'        </v-row>\n'
            f'      </variables>'
        )
    else:
        var_section = '      <variables fold="true">\n      </variables>'

    xml = (
        f'<?pithos version="1.0.0" ?>\n'
        f'<v-root style="height:100%">\n'
        f'  <v-dashboard\n'
        f'    theme="$operationBarToken.theme$"\n'
        f'    refresh-interval="$operationBarToken.refreshInterval$"\n'
        f'    scale-on-fullscreen="$operationBarToken.scaleOnFullscreen$"\n'
        f'    time="$operationBarToken.time$"\n'
        f'  >\n'
        f'    <v-operation-bar token="operationBarToken">\n'
        f'      <title>{_e(title)}</title>\n'
        f'      <description />\n'
        f'      <initial-value>\n'
        f'        <refresh-interval>{refresh_interval}</refresh-interval>\n'
        f'        <time>\n'
        f'          <earliest>{earliest}</earliest>{latest_xml}\n'
        f'        </time>\n'
        f'        <hide-on-fullscreen>{hide_fs}</hide-on-fullscreen>\n'
        f'        <scale-on-fullscreen>{scale}</scale-on-fullscreen>\n'
        f'        <layout-options>\n'
        f'          {_dict_to_xml_elements(layout_options, indent=10)}\n'
        f'        </layout-options>\n'
        f'      </initial-value>\n'
        f'{var_section}\n'
        f'    </v-operation-bar>\n'
        f'    <v-grid-layout options="$operationBarToken.layoutOptions$">\n'
        f'{chart_xml}\n'
        f'    </v-grid-layout>\n'
        f'  </v-dashboard>\n'
        f'</v-root>'
    )

    return xml, json.dumps(xml_vars)


# =============================================================================
# xml_to_chart_yaml — Pithos XML → YAML DSL
# =============================================================================


def xml_to_chart_yaml(xml_text, detail=None):
    """Parse Pithos XML back into chart DSL dict.

    Returns dict with: title, app, description, charts (list of chart dicts),
    dashboard config, and optional variables.
    """
    detail = detail or {}
    result = {
        "title": detail.get("title", ""),
        "app": detail.get("app", "search"),
        "description": detail.get("description", ""),
        "charts": [],
    }

    # Extract dashboard config from xmlVariables
    xv = detail.get("xmlVariables", {})
    obt = xv.get("operationBarToken", {}).get("value", {})
    if obt:
        result["dashboard"] = {
            "refresh_interval": obt.get("refreshInterval", "s30"),
            "time": obt.get("time", {}),
            "hide_on_fullscreen": obt.get("hideOnFullscreen", False),
            "scale_on_fullscreen": obt.get("scaleOnFullscreen", [0, 0]),
            "layout_options": obt.get("layoutOptions", {}),
        }

    # Extract user variables (exclude operationBarToken)
    user_vars = {}
    for k, v in xv.items():
        if k == "operationBarToken":
            continue
        user_vars[k] = v
    if user_vars:
        result["variables"] = user_vars

    # Parse <v-input> elements to enrich variables with input config
    v_inputs = re.findall(r'<v-input[^>]*>.*?</v-input>', xml_text or '', re.DOTALL)
    for vi in v_inputs:
        token = re.search(r'token="([^"]+)"', vi)
        if not token:
            continue
        token = token.group(1)
        inp_type = re.search(r'type="([^"]+)"', vi)
        inp_type = inp_type.group(1) if inp_type else 'text'
        label = re.search(r'<label[^>]*>([^<]*)</label>', vi)
        label = label.group(1) if label else token

        inp_config = {"type": inp_type, "label": label}

        sq = re.search(
            r'<search>.*?<query>(.*?)</query>.*?</search>', vi, re.DOTALL,
        )
        if sq:
            inp_config["search"] = {"query": sq.group(1).strip()}

        for key in (
            'field_for_label', 'field_for_value', 'auto_refresh',
            'select_all', 'value_prefix', 'value_suffix',
            'delimiter', 'multi_mode',
        ):
            m = re.search(
                rf'<{_snake_to_kebab(key)}>([^<]*)</{_snake_to_kebab(key)}>', vi,
            )
            if m:
                inp_config[key] = m.group(1)

        iv = re.search(
            r'<initial-value>(.*?)</initial-value>', vi, re.DOTALL,
        )
        if iv:
            val = iv.group(1).strip()
            try:
                parsed_iv = json.loads(val)
                inp_config["initial_value"] = (
                    parsed_iv if isinstance(parsed_iv, list) else val
                )
            except (json.JSONDecodeError, ValueError):
                inp_config["initial_value"] = val

        choices = re.findall(
            r'<choice\s+value="([^"]+)">([^<]*)</choice>', vi,
        )
        if choices:
            inp_config["choices"] = {cv: cl for cv, cl in choices}

        result.setdefault("variables", {})
        result["variables"].setdefault(token, {})
        result["variables"][token]["input"] = inp_config

    # Parse charts
    if not xml_text:
        return result

    layouts = re.findall(
        r'<v-layout\s[^>]*top="(\d+)"\s+left="(\d+)"\s+'
        r'width="(\d+)"\s+height="(\d+)"[^>]*>(.*?)</v-layout>',
        xml_text, re.DOTALL,
    )

    for top, left, width, height, body in layouts:
        if '<v-chart' not in body:
            continue

        chart = {
            "name": "Chart",
            "type": "area",
            "mode": "metric",
            "pos": {
                "x": int(left), "y": int(top),
                "w": int(width), "h": int(height),
            },
        }

        # Chart type
        ct = re.search(r'<v-chart[^>]*\s+type="([^"]+)"', body)
        if ct:
            chart["type"] = ct.group(1)

        # Name
        nm = re.search(
            r'<title>\s*<name>([^<]+)</name>.*?</title>', body, re.DOTALL,
        )
        if nm:
            chart["name"] = nm.group(1)

        # Flag/mode
        fl = re.search(r'<flag>(\w+)</flag>', body)
        if fl:
            chart["mode"] = "metric" if fl.group(1) == "metric" else "log"

        # Metric config
        mc = re.search(
            r'<metric-config>\s*(.*?)\s*</metric-config>', body, re.DOTALL,
        )
        if mc:
            try:
                mc_data = _parse_json(mc.group(1))
                if mc_data.get("metrics"):
                    m = mc_data["metrics"][0]
                    chart["metric"] = {
                        "key": m.get("key", ""),
                        "aggregation": m.get("aggregation", "avg"),
                        "unit": m.get("unit", "none"),
                    }
                    if m.get("groupBy"):
                        chart["metric"]["groupBy"] = m["groupBy"]
                    if mc_data.get("timeSpan"):
                        chart["metric"]["timeSpan"] = mc_data["timeSpan"]
                    if m.get("fns"):
                        for fn in m["fns"]:
                            if fn.get("type") == "sort":
                                cfg = fn.get("config", {})
                                chart["metric"]["sort"] = {
                                    "by": cfg.get("type", "avg"),
                                    "count": cfg.get("N", 10),
                                }
            except (json.JSONDecodeError, KeyError):
                pass
        else:
            # Raw SPL query — collapse all whitespace into single spaces
            qm = re.search(r'<query>\s*(.*?)\s*</query>', body, re.DOTALL)
            if qm:
                chart["query"] = re.sub(r'\s+', ' ', qm.group(1).strip())

        # Groups
        gm = re.search(r'<groups>(.*?)</groups>', body)
        if gm and gm.group(1) != "[]":
            try:
                chart["configs"] = chart.get("configs", {})
                chart["configs"]["groups"] = _parse_json(gm.group(1))
            except json.JSONDecodeError:
                pass

        # Y-axis fields
        fm = re.search(
            r'<y-axis>.*?<fields>(.*?)</fields>', body, re.DOTALL,
        )
        if fm and fm.group(1) != "[]":
            try:
                chart["configs"] = chart.get("configs", {})
                chart["configs"]["y_axis"] = chart["configs"].get("y_axis", {})
                chart["configs"]["y_axis"]["fields"] = _parse_json(fm.group(1))
            except json.JSONDecodeError:
                pass

        # Color metrics (single-value/KPI charts — metrics live in <color>)
        cm = re.search(
            r'<color>.*?<metrics>(.*?)</metrics>', body, re.DOTALL,
        )
        if cm and cm.group(1) != "[]":
            try:
                chart["configs"] = chart.get("configs", {})
                chart["configs"]["y_axis"] = chart["configs"].get("y_axis", {})
                chart["configs"]["y_axis"]["fields"] = _parse_json(cm.group(1))
            except json.JSONDecodeError:
                pass

        # X-axis field
        xm = re.search(
            r'<x-axis>.*?<field>([^<]+)</field>', body, re.DOTALL,
        )
        if xm and xm.group(1) != "_time":
            chart["configs"] = chart.get("configs", {})
            chart["configs"]["x_axis"] = chart["configs"].get("x_axis", {})
            chart["configs"]["x_axis"]["field"] = xm.group(1)

        result["charts"].append(chart)

    return result
