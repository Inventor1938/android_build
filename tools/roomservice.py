#!/usr/bin/env python
# Copyright (C) 2012 The CyanogenMod Project
# Copyright (C) 2012/2013 SlimRoms Project
# Copyright (C) 2017 The halogenOS Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
import os.path
import re
import subprocess
import sys
from xml.etree import ElementTree

try:
    # For python3
    import urllib.error
    import urllib.request
except ImportError:
    # For python2
    import imp
    import urllib2

    urllib = imp.new_module('urllib')
    urllib.error = urllib2
    urllib.request = urllib2

product = sys.argv[1]
api_url = "https://api.github.com/users/halogenOS/repos?page=%d"
if len(sys.argv) > 2:
    depsonly = sys.argv[2]
else:
    depsonly = None

try:
    device = product[product.index("_") + 1:]
except:
    device = product

if not depsonly:
    print "Device %s not found. Attempting to retrieve device repository from XOS Github (http://github.com/halogenOS)." % device

repositories = []

page = 1
while not depsonly:
    request = urllib.request.Request(api_url % page)
    api_file = os.getenv("HOME") + '/api_token'
    if (os.path.isfile(api_file)):
        infile = open(api_file, 'r')
        token = infile.readline()
        request.add_header('Authorization', 'token %s' % token.strip())
    result = json.loads(urllib2.urlopen(request).read())
    if len(result) == 0:
        break
    for res in result:
        repositories.append(res)
    page = page + 1

local_manifests = r'.repo/local_manifests'
if not os.path.exists(local_manifests): os.makedirs(local_manifests)

def exists_in_tree(lm, repository):
    for child in lm.getchildren():
        try:
            if child.attrib['path'].endswith(repository):
                return child
        except:
            pass
    return None

def exists_in_tree_device(lm, repository):
    for child in lm.getchildren():
        if child.attrib['name'].endswith(repository):
            return child
    return None

# in-place prettyprint formatter
def indent(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def get_from_manifest(devicename):
    try:
        lm = ElementTree.parse(".repo/local_manifests/XOS_manifest.xml")
        lm = lm.getroot()
    except:
        lm = ElementTree.Element("manifest")

    for localpath in lm.findall("project"):
        if re.search("android_device_.*_%s$" % device, localpath.get("name")):
            return localpath.get("path")

    # Devices originally from AOSP are in the main manifest...
    try:
        mm = ElementTree.parse(".repo/manifest.xml")
        mm = mm.getroot()
    except:
        mm = ElementTree.Element("manifest")

    for localpath in mm.findall("project"):
        if re.search("android_device_.*_%s$" % device, localpath.get("name")):
            return localpath.get("path")

    return None

def is_in_manifest(projectname, branch):
    try:
        lm = ElementTree.parse(".repo/local_manifests/XOS_manifest.xml")
        lm = lm.getroot()
    except:
        lm = ElementTree.Element("manifest")

    for localpath in lm.findall("project"):
        if localpath.get("name") == projectname and localpath.get("revision") == branch:
            return 1

    return None

def add_to_manifest_dependencies(repositories):
    try:
        lm = ElementTree.parse(".repo/local_manifests/XOS_manifest.xml")
        lm = lm.getroot()
    except:
        lm = ElementTree.Element("manifest")

    try:
        mlm = ElementTree.parse(".repo/manifests/default.xml")
        mlm = mlm.getroot()
    except Exception as e:
        mlm = ElementTree.Element("manifest")

    for repository in repositories:
        repo_name = repository['repository']
        repo_target = repository['target_path']
        try:
            repo_remote = repository['remote']
        except:
            repo_remote = "XOS"
            pass
        try:
            repo_revision = repository['branch']
        except:
            repo_revision = "XOS-7.1"
            pass
        existing_project = exists_in_tree(lm, repo_target)
        if existing_project != None:
            if existing_project.attrib['name'] != repository['repository']:
                print 'Updating dependency %s' % (repo_name)
                existing_project.set('name', repository['repository'])
            if existing_project.attrib['revision'] == repository['branch']:
                print 'halogenOS/%s already exists' % (repo_name)
            else:
                print 'updating branch for %s to %s' % (repo_name, repository['branch'])
                existing_project.set('revision', repository['branch'])
            continue
        existing_m_project = exists_in_tree(mlm, repo_target)
        if existing_m_project != None:
            if existing_m_project.attrib['path'] == repository['target_path']:
                print '%s already exists in main manifest, replacing with new dep' % (repo_name)
                lm.append(ElementTree.Element("remove-project", attrib = {
                    "name": existing_m_project.attrib['name']
                }))

        print 'Adding dependency: %s -> %s' % (repo_name, repo_target)
        project = ElementTree.Element("project", attrib = { "path": repo_target,
            "remote": repo_remote, "name": repo_name, "revision": repo_revision })

        if 'branch' in repository:
            project.set('revision',repository['branch'])

        lm.append(project)

    indent(lm, 0)
    raw_xml = ElementTree.tostring(lm)
    raw_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + raw_xml

    f = open('.repo/local_manifests/XOS_manifest.xml', 'w')
    f.write(raw_xml)
    f.close()

def add_to_manifest(repositories):
    try:
        lm = ElementTree.parse(".repo/local_manifests/XOS_manifest.xml")
        lm = lm.getroot()
    except:
        lm = ElementTree.Element("manifest")

    for repository in repositories:
        repo_name = repository['repository']
        repo_target = repository['target_path']
        try:
            branch = repository['branch']
        except KeyError:
            branch = 'XOS-7.1'
        try:
            remote = repository['remote']
        except KeyError:
            remote = 'XOS'
        existing_project = exists_in_tree_device(lm, repo_name)
        if existing_project is not None:
            if existing_project.attrib['revision'] == branch:
                print '%s already exists' % repo_name
            else:
                print 'updating branch for %s to %s' % (repo_name, branch)
                existing_project.set('revision', branch)
            continue

        print 'Adding dependency: %s -> %s' % (repo_name, repo_target)
        project = ElementTree.Element("project", attrib={"path": repo_target,
                                                         "remote": remote, "name": "%s" % repo_name,
                                                         "revision": branch})

        lm.append(project)

    indent(lm, 0)
    raw_xml = ElementTree.tostring(lm)
    raw_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + raw_xml

    f = open('.repo/local_manifests/XOS_manifest.xml', 'w')
    f.write(raw_xml)
    f.close()

def fetch_dependencies(repo_path):
    print 'Looking for dependencies'
    dependencies_path = repo_path + '/XOS.dependencies'
    syncable_repos = []

    if os.path.exists(dependencies_path):
        dependencies_file = open(dependencies_path, 'r')
        dependencies = json.loads(dependencies_file.read())
        fetch_list = []

        for dependency in dependencies:
            if not is_in_manifest("%s" % dependency['repository'], "%s" % dependency['branch']):
                fetch_list.append(dependency)
                syncable_repos.append(dependency['target_path'])

        dependencies_file.close()

        if len(fetch_list) > 0:
            print 'Adding dependencies to manifest'
            add_to_manifest_dependencies(fetch_list)
    else:
        print 'Dependencies file not found, bailing out.'

    if len(syncable_repos) > 0:
        print 'Syncing dependencies'
        for repo in syncable_repos:
            subprocess.call(['repo', 'sync', '--force-sync', repo])

if depsonly:
    repo_path = get_from_manifest(device)
    if repo_path:
        fetch_dependencies(repo_path)
    else:
        print "Trying dependencies-only mode on a non-existing device tree?"

    sys.exit()

else:
    for repository in repositories:
        repo_name = repository['name']
        if repo_name.startswith("android_device_") and repo_name.endswith("_" + device):
            print "Found repository: %s" % repository['name']
            manufacturer = repo_name.replace("android_device_", "").replace("_" + device, "")

            repo_path = "device/%s/%s" % (manufacturer, device)

            add_to_manifest([{'repository':repo_name,'target_path':repo_path,'branch':'XOS-7.1'}])

            print "Syncing repository to retrieve project."
            subprocess.call(['repo', 'sync', '--force-sync', repo_path])
            print "Repository synced!"

            fetch_dependencies(repo_path)
            print "Done"
            sys.exit()

print "Repository for %s not found in the XOS Github repository list. If this is in error, you may need to manually add it to .repo/local_manifests/XOS_manifest.xml" % device
