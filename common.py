'''
Copyright (c) 2017 VMware, Inc. All Rights Reserved.
SPDX-License-Identifier: BSD-2-Clause
'''

import logging

from classes.package import Package
from classes.notice import Notice
from command_lib import command_lib as cmdlib
from report import info
from report import errors
from utils import cache as cache
from utils import constants as const
from utils.container import check_container
'''
Common functions
'''

# global logger
logger = logging.getLogger('ternlog')


def load_from_cache(image):
    '''Given an image object, check against cache to see if a layer id exists
    if yes then get the package list and load it in the image layer. If it
    doesn't exist continue. If not all the layers have packages, return False
    else return True'''
    is_full = True
    for layer in image.layers:
        if not layer.packages:
            raw_pkg_list = cache.get_packages(layer.id)
            if not raw_pkg_list:
                is_full = False
            else:
                from_cache_notice = Notice()
                from_cache_notice.origin = image.get_image_option() + \
                    layer.id
                from_cache_notice.message = info.loading_from_cache.format(
                    layer_id=layer.id)
                from_cache_notice.level = 'info'
                layer.add_notice(from_cache_notice)
                for pkg_dict in raw_pkg_list:
                    pkg = Package(pkg_dict['name'])
                    pkg.fill(pkg_dict)
                    layer.add_package(pkg)
    return image, is_full


def add_base_packages(image, info):
    '''Given an image object, get a list of package objects from
    invoking the commands in the command library base section:
        1. For the image and tag name find if there is a list of package names
        2. If there is an invoke dictionary, invoke the commands
        3. Create a list of packages
        4. Add them to the image'''
    # information under the base image tag in the command library
    listing = cmdlib.get_base_listing(image.name, image.tag)
    origin = 'command_lib/base.yml'
    if listing:
        shell, msg = cmdlib.get_image_shell(listing)
        if not shell:
            # add a warning notice for no shell in the command library
            no_shell_message = errors.no_shell_listing.format(
                image_name=image.name, image_tag=image.tag,
                default_shell=const.shell)
            no_shell_notice = Notice(origin, no_shell_message, 'warning')
            image.add_notice(no_shell_notice)
            # add a hint notice to add the shell to the command library
            add_shell_message = errors.no_listing_for_base_key.format(
                listing_key='shell')
            add_shell_notice = Notice(origin, add_shell_message, 'hint')
            image.add_notice(add_shell_notice)
            shell = const.shell
        # check if a container is running first
        # eventually this needs to change to use derivatives that have
        # more than 1 layer
        # for now, we add the list of packages to all the layers in a
        # starting base image
        if check_container():
            names, n_msg = cmdlib.get_pkg_attr_list(shell, info['names'])
            versions, v_msg = cmdlib.get_pkg_attr_list(shell, info['versions'])
            licenses, l_msg = cmdlib.get_pkg_attr_list(shell, info['licenses'])
            src_urls, u_msg = cmdlib.get_pkg_attr_list(shell, info['src_urls'])
            # add a notice to the image if something went wrong
            invoke_msg = n_msg + v_msg + l_msg + u_msg
            if invoke_msg:
                pkg_invoke_notice = Notice(origin, invoke_msg, 'error')
                image.add_notice(pkg_invoke_notice)
            if names and len(names) > 1:
                for index in range(0, len(names)):
                    pkg = Package(names[index])
                    if len(versions) == len(names):
                        pkg.version = versions[index]
                    if len(licenses) == len(names):
                        pkg.license = licenses[index]
                    if len(src_urls) == len(names):
                        pkg.src_url = src_urls[index]
                        for layer in image.layers:
                            layer.add_package(pkg)
            # add all the packages to the cache
            for layer in image.layers:
                cache.add_layer(layer)
        # if no container is running give a logging error
        else:
            logger.error(errors.no_running_docker_container)
    # if there is no listing add a notice
    else:
        no_listing_notice = Notice(origin, errors.no_image_tag_listing.format(
            image_name=image.name, image_tag=image.tag), 'error')
        image.add_notice(no_listing_notice)


def fill_package_metadata(pkg_obj, pkg_listing, shell):
    '''Given a Package object and the Package listing from the command
    library, fill in the attribute value returned from looking up the
    data and methods of the package listing.
    Fill out: version, license and src_url
    If there are errors, fill out notices'''
    origin = 'command_lib/snippets.yml'
    # version
    version_listing, listing_msg = cmdlib.check_library_key(
        pkg_listing, 'version')
    if version_listing:
        version_list, invoke_msg = cmdlib.get_pkg_attr_list(
            shell, version_listing, package_name=pkg_obj.name)
        if version_list:
            pkg_obj.version = version_list[0]
        else:
            version_invoke_error_notice = Notice(origin, invoke_msg, 'error')
            pkg_obj.add_notice(version_invoke_error_notice)
    else:
        no_version_listing_notice = Notice(origin, listing_msg, 'warning')
        pkg_obj.add_notice(no_version_listing_notice)
    # license
    license_listing, listing_msg = cmdlib.check_library_key(
        pkg_listing, 'license')
    if license_listing:
        license_list, invoke_msg = cmdlib.get_pkg_attr_list(
            shell, license_listing, package_name=pkg_obj.name)
        if license_list:
            pkg_obj.license = license_list[0]
        else:
            license_invoke_error_notice = Notice(origin, invoke_msg, 'error')
            pkg_obj.add_notice(license_invoke_error_notice)
    else:
        no_license_listing_notice = Notice(origin, listing_msg, 'warning')
        pkg_obj.add_notice(no_license_listing_notice)
    # src_urls
    url_listing, listing_msg = cmdlib.check_library_key(
        pkg_listing, 'license')
    if url_listing:
        url_list, invoke_msg = cmdlib.get_pkg_attr_list(
            shell, url_listing, package_name=pkg_obj.name)
        if url_list:
            pkg_obj.src_url = url_list[0]
        else:
            url_invoke_error_notice = Notice(origin, invoke_msg, 'error')
            pkg_obj.add_notice(url_invoke_error_notice)
    else:
        no_url_listing_notice = Notice(origin, listing_msg, 'warning')
        pkg_obj.add_notice(no_url_listing_notice)


def get_package_dependencies(package_listing, package_name, shell):
    '''The package listing is the result of looking up the command name in the
    command library. Given this listing, the package name and the shell
    return a list of package dependency names'''
    deps_listing, deps_msg = cmdlib.check_library_key(package_listing, 'deps')
    if deps_listing:
        deps_list, invoke_msg = cmdlib.get_pkg_attr_list(
            shell, deps_listing, package_name=package_name)
        if deps_list:
            return list(set(deps_list)), ''
        else:
            return [], invoke_msg
    else:
        return [], deps_msg


def get_installed_packages(command):
    '''Given a Command object, return a list of package objects'''
    pkgs = []
    # check if the command attributes are set
    if command.is_set() and command.is_install():
        for word in command.words:
            pkg = Package(word)
            pkgs.append(pkg)
    return pkgs


def remove_ignored_commands(command_list):
    '''For a list of Command objects, examine if the command is ignored.
    Return all the ignored command strings. This is a filtering operation
    so all the ignored command objects will be removed from the original
    list'''
    ignore_commands = ''
    filtered_list = []
    while command_list:
        command = command_list.pop(0)
        if command.is_set() and command.is_ignore():
            ignore_commands = ignore_commands + command.shell_command + '\n'
        else:
            filtered_list.append(command)
    return ignore_commands, filtered_list


def remove_unrecognized_commands(command_list):
    '''For a list of Command objects, examine if the command is not recognized.
    Return all the unrecognized command strings. This is a filtering operation
    so all the unrecognized command objects will be removed from the original
    list'''
    unrec_commands = ''
    filtered_list = []
    while command_list:
        command = command_list.pop(0)
        if not command.is_set():
            unrec_commands = unrec_commands + command.shell_command + '\n'
        else:
            filtered_list.append(command)
    return unrec_commands, filtered_list
