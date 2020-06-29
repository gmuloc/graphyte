#!/usr/bin/env python3
"""template_utils.py

Tools to assist with graphyte template processing.

"""

# imports
import logging
import os
import re
from param_utils import param_is_false_positive, param_is_legal
import pprint

pp = pprint.PrettyPrinter(indent=4)

# info
__author__ = "Jorge Somavilla"

# initialize logger
logger = logging.getLogger('graphyte')


def add_templates_to_script(gm, merge_duplicate_vars="no"):
    """Transforms template text files into JS <script>
    arrays to be embedded in the final HTML module.
    Extracts parameters for validation while doing so.

    :param gm: the graphyte module object
    :param merge_duplicate_vars: a variable indicating whether
                                 or not to merge duplicate variables
                                 in templates in the module variables
                                 table.
                                 There are three behaviors:
                                 * no (default for backward compatibility) means there will be
                                  one line per variables apparition in
                                  templates
                                * file - gives a granularity at file level to merge the variables
                                  together
                                * all - means that all variables in all templates
                                  with the same name will be merged as one
    :return: file_script, templates in JS <script> array format.
    """

    logger.info('         Processing template files...' + '\r\n')
    if merge_duplicate_vars not in ['no', 'file', 'all']:
        raise ValueError("merge_duplicate_vars must be in ['no', 'file', 'all'], "
                         "{} was given".format(merge_duplicate_vars))

    file_script = ""

    # mod_linked_templates['templates'] = {}
    mod_linked_templates = {}
    # global structure for template parameteres converted to CSV at the end
    template_params_dict = {}

    for dirpath, dirs, src_files in os.walk(gm.file_dir):
        for src_file_name in src_files:
            # Check if file has been linked or is Changes file
            if not(src_file_name in gm.svg_links or src_file_name == gm.changes_fname):
                continue

            # Link to file has been found in the SVG or is Changes file, process it.
            logger.info('             ' + src_file_name + '\r\n')
            file_path = os.path.join(dirpath, src_file_name)

            if not os.path.isfile(file_path):
                # Hmmm maybe should emit some log here?
                continue

            file_name = os.path.splitext(src_file_name)[0]
            # mod_linked_templates['templates'][src_file_name]=file_path
            if not src_file_name == gm.changes_fname:
                # do not add changesfile to module templates dict
                mod_linked_templates[src_file_name] = file_path
            # spaces dots or hyphens -> underscores
            file_name = re.sub(r'\s|-|\.|\(|\)|\+', r'_',
                               file_name.rstrip()
                               )
            file_ext = os.path.splitext(src_file_name)[1]
            file_ext = re.sub(r'\.', r'_', file_ext.rstrip())
            file_script += "    var v_" + file_name + file_ext \
                           + " = [\n \"" + src_file_name
            with open(file_path, encoding="utf8", errors='ignore') as f:
                for line in f:
                    line = re.sub(r'(\\|\")', r'\\\1', line.rstrip())
                    line = re.sub(r'-', r'\-', line.rstrip())
                    line = re.sub(r'</script>', r'<\/script>', line.rstrip())
                    # line = line.decode('utf-8')
                    file_script += "\",\n\"" + line.rstrip()
                file_script += "\"];\n\n"

            # Find decision parameters
            if file_ext == "_yang" or file_ext == "_xml" or src_file_name == gm.changes_fname:
                # do nothing
                continue

            if file_ext == "_csv":
                with open(file_path, encoding="utf8", errors='ignore') as f:
                    for line in f:
                        if not (line.strip() == ""):
                            items = line.strip().split(",")
                            # items.insert(1,src_file_name)
                            newline = items[0] + "," \
                                + src_file_name + ","
                            if gm.in_xls_path:
                                # define legality of parameter
                                param_validation_result = "ok"
                                # print "Legal?:" + items[0]
                                if not(param_is_legal(items[0], gm)):
                                    param_validation_result = "unauthorized"
                                    gm.invalid_param_found_alert = "(!)"

                                newline += param_validation_result + ","

                            for item in items[1:-1]:
                                newline += item + " | "
                            newline += items[-1]
                            gm.decision_param_list.append(newline + "\n")

            else:
                # txt + others
                # Find template parameters
                # if file_ext == "_txt":
                with open(file_path, encoding="utf8", errors='ignore') as f:
                    for line in f:
                        line.encode('utf-8').strip()
                        matches = re.findall(r'(<.*?>)', line, re.S)
                        if matches:
                            for paramfound in matches:
                                if not param_is_false_positive(paramfound):
                                    # merge behavior
                                    # all
                                    if paramfound in template_params_dict.keys():
                                        if src_file_name in template_params_dict[paramfound]["src"].keys():
                                            template_params_dict[paramfound]["src"][src_file_name].append(re.sub(r',', r'', line.strip()))
                                        else:
                                            template_params_dict[paramfound]["src"][src_file_name] = [re.sub(r',', r'', line.strip())]
                                    else:
                                        template_params_dict[paramfound] = {"src": {src_file_name: [re.sub(r',', r'', line.strip())]}}
                                        if gm.in_xls_path:
                                            template_params_dict[paramfound]['validation'] = "ok"
                                            if not(param_is_legal(paramfound, gm)):
                                                template_params_dict[paramfound]['validation'] = "unauthorized"
                                                gm.invalid_param_found_alert = "(!)"

    # Now append dictionary to gm.template_param_list:
    if merge_duplicate_vars == "all":
        for param, fields in template_params_dict.items():
            line = param + ","
            srcs = ""
            lines = ""
            for src, data in fields["src"].items():
                srcs += src + "\\n"
                for lf in data:
                   lines += lf + "\\n***\\n"
            line += srcs[:-1] + ","
            if "validation" in fields.keys():
                line += fields['validation'] + ","
            line += lines[:-1] + ","
            gm.template_param_list.append(line)

    elif merge_duplicate_vars == "file":
        for param, fields in template_params_dict.items():
            for src,data in fields["src"].items():
                line = param + "," + src + ","
                if "validation" in fields.keys():
                    line += fields['validation'] + ","
                for lf in data:
                    line += lf + "\\n***\\n"
                line = line[:-1]
                gm.template_param_list.append(line)

    else:
        # merge_duplicate_vars== "no" - though should add an error case
        for param, fields in template_params_dict.items():
            for src,data in fields["src"].items():
                for lf in data:
                    line = param + "," + src + ","
                    if "validation" in fields.keys():
                        line += fields['validation'] + ","
                    line += lf
                    gm.template_param_list.append(line)

    logger.debug(gm.template_param_list)


    logger.info('         ...ok' + '\r\n')
    mod_linked_templates2 = dict()
    mod_linked_templates2['templates'] = {}
    mod_linked_templates2['templates'] = mod_linked_templates
    return file_script,mod_linked_templates2
