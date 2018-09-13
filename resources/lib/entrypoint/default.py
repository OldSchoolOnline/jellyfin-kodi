# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import sys
import urlparse
import urllib
import os
import sys

import xbmc
import xbmcvfs
import xbmcgui
import xbmcplugin
import xbmcaddon

import client
from database import reset, get_sync, Database, emby_db, get_credentials
from objects import Objects, Actions
from downloader import TheVoid
from helper import _, event, settings, window, dialog, api, JSONRPC
from emby import Emby

#################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

#################################################################################################


class Events(object):


    def __init__(self):

        ''' Parse the parameters. Reroute to our service.py
            where user is fully identified already.
        '''
        base_url = sys.argv[0]
        path = sys.argv[2]

        try:
            params = dict(urlparse.parse_qsl(path[1:]))
        except Exception:
            params = {}

        mode = params.get('mode')
        server = params.get('server')

        if server == 'None':
            server = None

        LOG.warn("path: %s params: %s", path, json.dumps(params, indent=4))

        if '/extrafanart' in base_url:

            emby_path = path[1:]
            emby_id = params.get('id')
            get_fanart(emby_id, emby_path, server)

        elif '/Extras' in base_url or '/VideoFiles' in base_url:

            emby_path = path[1:]
            emby_id = params.get('id')
            get_video_extras(emby_id, emby_path, server)

        elif mode =='play':

            item = TheVoid('GetItem', {'Id': params['id'], 'ServerId': server}).get()
            Actions(params.get('server')).play(item, params.get('dbid'), playlist=params.get('playlist') == 'true')

        elif mode == 'playlist':
            event('PlayPlaylist', {'Id': params['id'], 'ServerId': server})
        elif mode == 'deviceid':
            client.reset_device_id()
        elif mode == 'reset':
            reset()
        elif mode == 'delete':
            delete_item()
        elif mode == 'refreshboxsets':
            event('SyncLibrary', {'Id': "Boxsets:Refresh"})
        elif mode == 'nextepisodes':
            get_next_episodes(params['id'], params['limit'])
        elif mode == 'browse':
            browse(params.get('type'), params.get('id'), params.get('folder'), server)
        elif mode == 'synclib':
            event('SyncLibrary', {'Id': params.get('id')})
        elif mode == 'repairlib':
            event('RepairLibrary', {'Id': params.get('id')})
        elif mode == 'removelib':
            event('RemoveLibrary', {'Id': params.get('id')})
        elif mode == 'repairlibs':
            event('RepairLibrarySelection')
        elif mode == 'updatelibs':
            event('SyncLibrarySelection')
        elif mode == 'addlibs':
            event('AddLibrarySelection')
        elif mode == 'connect':
            event('EmbyConnect')
        elif mode == 'addserver':
            event('AddServer')
        elif mode == 'login':
            event('ServerConnect', {'Id': server})
        elif mode == 'removeserver':
            event('RemoveServer', {'Id': server})
        elif mode == 'settings':
            xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby)')
        elif mode == 'adduser':
            add_user()
        elif mode == 'checkupdate':
            event('CheckUpdate')
        elif mode == 'updateserver':
            event('UpdateServer')
        elif mode == 'thememedia':
            get_themes()
        else:
            listing()


def listing():

    ''' Display all emby nodes and dynamic entries when appropriate.
    '''
    total = int(window('Emby.nodes.total') or 0)
    sync = get_sync()
    whitelist = [x.replace('Mixed:', "") for x in sync['Whitelist']]
    servers = get_credentials()['Servers'][1:]

    for i in range(total):

        window_prop = "Emby.nodes.%s" % i
        path = window('%s.index' % window_prop)

        if not path:
            path = window('%s.content' % window_prop) or window('%s.path' % window_prop)

        label = window('%s.title' % window_prop)
        node = window('%s.type' % window_prop)
        artwork = window('%s.artwork' % window_prop)
        view_id = window('%s.id' % window_prop)
        context = []

        if view_id and node in ('movies', 'tvshows', 'musicvideos', 'music') and view_id not in whitelist:
            context.append((_(33123), "RunPlugin(plugin://plugin.video.emby?mode=synclib&id=%s)" % view_id))

        if view_id and node in ('movies', 'tvshows', 'musicvideos', 'music') and view_id in whitelist:

            context.append((_(33136), "RunPlugin(plugin://plugin.video.emby?mode=synclib&id=%s)" % view_id))
            context.append((_(33132), "RunPlugin(plugin://plugin.video.emby?mode=repairlib&id=%s)" % view_id))
            context.append((_(33133), "RunPlugin(plugin://plugin.video.emby?mode=removelib&id=%s)" % view_id))

        LOG.debug("--[ listing/%s/%s ] %s", node, label, path)
        
        if path:
            if xbmc.getCondVisibility('Window.IsActive(Pictures)') and node in ('photos', 'homevideos'):
                directory(label, path, artwork=artwork)
            elif xbmc.getCondVisibility('Window.IsActive(Videos)') and node not in ('photos', 'homevideos', 'music', 'books', 'audiobooks'):
                directory(label, path, artwork=artwork, context=context)
            elif xbmc.getCondVisibility('Window.IsActive(Music)') and node in ('music', 'books', 'audiobooks'):
                directory(label, path, artwork=artwork, context=context)
            elif not xbmc.getCondVisibility('Window.IsActive(Videos) | Window.IsActive(Pictures) | Window.IsActive(Music)'):
                directory(label, path, artwork=artwork)

    for server in servers:
        context = []

        if server.get('ManualAddress'):
            context.append((_(33141), "RunPlugin(plugin://plugin.video.emby/?mode=removeserver&server=%s)" % server['Id']))

        if 'AccessToken' not in server:
            directory("%s (%s)" % (server['Name'], _(30539)), "plugin://plugin.video.emby/?mode=login&server=%s" % server['Id'], False, context=context)
        else:
            directory(server['Name'], "plugin://plugin.video.emby/?mode=browse&server=%s" % server['Id'], context=context)


    directory(_(33134), "plugin://plugin.video.emby/?mode=addserver", False)
    directory(_(5), "plugin://plugin.video.emby/?mode=settings", False)
    directory(_(33054), "plugin://plugin.video.emby/?mode=adduser", False)
    directory(_(33098), "plugin://plugin.video.emby/?mode=refreshboxsets", False)
    directory(_(33154), "plugin://plugin.video.emby/?mode=addlibs", False)
    directory(_(33139), "plugin://plugin.video.emby/?mode=updatelibs", False)
    directory(_(33140), "plugin://plugin.video.emby/?mode=repairlibs", False)
    directory(_(33060), "plugin://plugin.video.emby/?mode=thememedia", False)
    directory(_(33058), "plugin://plugin.video.emby/?mode=reset", False)
    directory(_(33163), None, False, artwork="special://home/addons/plugin.video.emby/donations.png")

    xbmcplugin.setContent(int(sys.argv[1]), 'files')
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

def directory(label, path, folder=True, artwork=None, fanart=None, context=None):

    ''' Add directory listitem. context should be a list of tuples [(label, action)*]
    '''
    li = dir_listitem(label, path, artwork, fanart)

    if context:
        li.addContextMenuItems(context)

    xbmcplugin.addDirectoryItem(int(sys.argv[1]), path, li, folder)

    return li

def dir_listitem(label, path, artwork=None, fanart=None):

    li = xbmcgui.ListItem(label, path=path)
    li.setThumbnailImage(artwork or "special://home/addons/plugin.video.emby/icon.png")
    li.setArt({"fanart": fanart or "special://home/addons/plugin.video.emby/fanart.jpg"})
    li.setArt({"landscape": artwork or fanart or "special://home/addons/plugin.video.emby/fanart.jpg"})

    return li

def browse(media, view_id=None, folder=None, server_id=None):

    ''' Browse content dynamically.
    '''
    LOG.info("--[ v:%s/%s ] %s", view_id, media, folder)

    if not window('emby_online.bool') and server_id is None:
        LOG.error("Default server is not online.")

        return

    if view_id:

        view = TheVoid('GetItem', {'ServerId': server_id, 'Id': view_id}).get()
        xbmcplugin.setPluginCategory(int(sys.argv[1]), view['Name'])

    content_type = "files"

    if media in ('tvshows', 'seasons', 'episodes', 'movies', 'musicvideos'):
        content_type = media
    elif media in ('homevideos', 'photos'):
        content_type = "images"

    if folder == 'FavEpisodes':
        listing = TheVoid('Browse', {'Media': "Episode", 'ServerId': server_id, 'Limit': 25, 'Filters': ["IsFavorite"]}).get()
    elif media == 'homevideos':
        listing = TheVoid('Browse', {'Id': folder or view_id, 'Media': "Video,Folder,PhotoAlbum,Photo", 'ServerId': server_id, 'Recursive': False}).get()
    elif media == 'movies':
        listing = TheVoid('Browse', {'Id': folder or view_id, 'Media': "Movie,Boxset", 'ServerId': server_id, 'Recursive': True}).get()
    elif media in ('boxset', 'library'):
        listing = TheVoid('Browse', {'Id': folder or view_id, 'ServerId': server_id, 'Recursive': True}).get()
    elif media == 'episodes':
        listing = TheVoid('Browse', {'Id': folder or view_id, 'Media': "Episode", 'ServerId': server_id, 'Recursive': True}).get()
    elif media == 'boxsets':
        listing = TheVoid('Browse', {'Id': folder or view_id, 'ServerId': server_id, 'Recursive': False, 'Filters': ["Boxsets"]}).get()
    else:
        listing = TheVoid('Browse', {'Id': folder or view_id, 'ServerId': server_id, 'Recursive': False}).get()


    if listing and listing.get('Items'):

        actions = Actions(server_id)
        list_li = []

        for item in listing['Items']:

            li = xbmcgui.ListItem()
            li.setProperty('embyid', item['Id'])
            li.setProperty('embyserver', server_id)
            actions.set_listitem(item, li)

            if item.get('IsFolder'):

                params = {
                    'id': view_id or item['Id'],
                    'mode': "browse",
                    'type': get_folder_type(item) or media,
                    'folder': item['Id'],
                    'server': server_id
                }
                path = "%s?%s" % ("plugin://plugin.video.emby",  urllib.urlencode(params))
                context = []

                if item['Type'] in ('Series', 'Season', 'Playlist'):
                    context.append(("Play", "RunPlugin(plugin://plugin.video.emby?mode=playlist&id=%s&server=%s)" % (item['Id'], server_id)))

                if item['UserData']['Played']:
                    context.append((_(16104), "RunPlugin(plugin://plugin.video.emby?mode=unwatched&id=%s&server=%s)" % (item['Id'], server_id)))
                else:
                    context.append((_(16103), "RunPlugin(plugin://plugin.video.emby?mode=watched&id=%s&server=%s)" % (item['Id'], server_id)))

                li.addContextMenuItems(context)
                list_li.append((path, li, True))
            else:
                if item['Type'] not in ('Photo', 'PhotoAlbum'):
                    params = {
                        'id': item['Id'],
                        'mode': "play",
                        'server': server_id
                    }
                    path = "%s?%s" % ("plugin://plugin.video.emby", urllib.urlencode(params))
                    li.setProperty('path', path)
                    context = [(_(13412), "RunPlugin(plugin://plugin.video.emby?mode=playlist&id=%s&server=%s)" % (item['Id'], server_id))]

                    if item['UserData']['Played']:
                        context.append((_(16104), "RunPlugin(plugin://plugin.video.emby?mode=unwatched&id=%s&server=%s)" % (item['Id'], server_id)))
                    else:
                        context.append((_(16103), "RunPlugin(plugin://plugin.video.emby?mode=watched&id=%s&server=%s)" % (item['Id'], server_id)))

                    li.addContextMenuItems(context)

                list_li.append((li.getProperty('path'), li, False))

        xbmcplugin.addDirectoryItems(int(sys.argv[1]), list_li, len(list_li))

    if content_type == 'images':
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_TITLE)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_DATE)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_RATING)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)

    xbmcplugin.setContent(int(sys.argv[1]), content_type)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

def get_folder_type(item):

    media = item['Type']

    if media == 'Series':
        return "seasons"
    elif media == 'Season':
        return "episodes"
    elif media == 'BoxSet':
        return "boxset"
    elif media == 'MusicArtist':
        return "albums"
    elif media == 'MusicAlbum':
        return "songs"
    elif media == 'CollectionFolder':
        return item.get('CollectionType', 'library')

def get_fanart(item_id, path, server_id=None):
    
    ''' Get extra fanart for listitems. This is called by skinhelper.
        Images are stored locally, due to the Kodi caching system.
    '''
    if not item_id and 'plugin.video.emby' in path:
        item_id = path.split('/')[-2]

    if not item_id:
        return

    LOG.info("[ extra fanart ] %s", item_id)
    objects = Objects()
    list_li = []
    API = api.API(item, TheVoid('GetServerAddress', {'ServerId': server_id}).get())
    directory = xbmc.translatePath("special://thumbnails/emby/%s/" % item_id).decode('utf-8')

    if not xbmcvfs.exists(directory):

        xbmcvfs.mkdirs(directory)
        item = TheVoid('GetItem', {'ServerId': server_id, 'Id': item_id}).get()
        obj = objects.map(item, 'Artwork')
        backdrops = API.get_all_artwork(obj)
        tags = obj['BackdropTags']

        for index, backdrop in enumerate(backdrops):

            tag = tags[index]
            fanart = os.path.join(directory, "fanart%s.jpg" % tag)
            li = xbmcgui.ListItem(tag, path=fanart)
            xbmcvfs.copy(backdrop, fanart)
            list_li.append((fanart, li, False))
    else:
        LOG.debug("cached backdrop found")
        dirs, files = xbmcvfs.listdir(directory)

        for file in files:
            fanart = os.path.join(directory, file.decode('utf-8'))
            li = xbmcgui.ListItem(file, path=fanart)
            list_li.append((fanart, li, False))

    xbmcplugin.addDirectoryItems(int(sys.argv[1]), list_li, len(list_li))
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

def get_video_extras(item_id, path, server_id=None):

    ''' Returns the video files for the item as plugin listing, can be used
        to browse actual files or video extras, etc.
    '''
    if not item_id and 'plugin.video.emby' in path:
        item_id = path.split('/')[-2]

    if not item_id:
        return

    item = TheVoid('GetItem', {'ServerId': server_id, 'Id': item_id}).get()
    # TODO

    """
    def getVideoFiles(embyId,embyPath):
        #returns the video files for the item as plugin listing, can be used for browsing the actual files or videoextras etc.
        emby = embyserver.Read_EmbyServer()
        if not embyId:
            if "plugin.video.emby" in embyPath:
                embyId = embyPath.split("/")[-2]
        if embyId:
            item = emby.getItem(embyId)
            putils = playutils.PlayUtils(item)
            if putils.isDirectPlay():
                #only proceed if we can access the files directly. TODO: copy local on the fly if accessed outside
                filelocation = putils.directPlay()
                if not filelocation.endswith("/"):
                    filelocation = filelocation.rpartition("/")[0]
                dirs, files = xbmcvfs.listdir(filelocation)
                for file in files:
                    file = filelocation + file
                    li = xbmcgui.ListItem(file, path=file)
                    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=file, listitem=li)
                for dir in dirs:
                    dir = filelocation + dir
                    li = xbmcgui.ListItem(dir, path=dir)
                    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=dir, listitem=li, isFolder=True)
        #xbmcplugin.endOfDirectory(int(sys.argv[1]))
    """

def get_next_episodes(item_id, limit):
    
    ''' Only for synced content.
    '''
    with Database('emby') as embydb:

        db = emby_db.EmbyDatabase(embydb.cursor)
        library = db.get_view_name(item_id)

        if not library:
            return

    result = JSONRPC('VideoLibrary.GetTVShows').execute({
                'sort': {'order': "descending", 'method': "lastplayed"},
                'filter': {
                    'and': [
                        {'operator': "true", 'field': "inprogress", 'value': ""},
                        {'operator': "is", 'field': "tag", 'value': "%s" % library}
                    ]},
                'properties': ['title', 'studio', 'mpaa', 'file', 'art']
             })

    try:
        items = result['result']['tvshows']
    except (KeyError, TypeError):
        return

    list_li = []

    for item in items:
        if settings('ignoreSpecialsNextEpisodes.bool'):
            params = {
                'tvshowid': item['tvshowid'],
                'sort': {'method': "episode"},
                'filter': {
                    'and': [
                        {'operator': "lessthan", 'field': "playcount", 'value': "1"},
                        {'operator': "greaterthan", 'field': "season", 'value': "0"}
                ]},
                'properties': [
                    "title", "playcount", "season", "episode", "showtitle",
                    "plot", "file", "rating", "resume", "tvshowid", "art",
                    "streamdetails", "firstaired", "runtime", "writer",
                    "dateadded", "lastplayed"
                ],
                'limits': {"end": 1}
            }
        else:
            params = {
                'tvshowid': item['tvshowid'],
                'sort': {'method': "episode"},
                'filter': {'operator': "lessthan", 'field': "playcount", 'value': "1"},
                'properties': [
                    "title", "playcount", "season", "episode", "showtitle",
                    "plot", "file", "rating", "resume", "tvshowid", "art",
                    "streamdetails", "firstaired", "runtime", "writer",
                    "dateadded", "lastplayed"
                ],
                'limits': {"end": 1}
            }

        result = JSONRPC('VideoLibrary.GetEpisodes').execute(params)

        try:
            episodes = result['result']['episodes']
        except (KeyError, TypeError):
            pass
        else:
            for episode in episodes:

                li = create_listitem(episode)
                list_li.append((episode['file'], li))

        if len(list_li) == limit:
            break

    xbmcplugin.addDirectoryItems(int(sys.argv[1]), list_li, len(list_li))
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

def create_listitem(item):

    ''' Listitem based on jsonrpc items.
    '''
    title = item['title']
    label2 = ""
    li = xbmcgui.ListItem(title)
    li.setProperty('IsPlayable', "true")
    
    metadata = {
        'Title': title,
        'duration': str(item['runtime']/60),
        'Plot': item['plot'],
        'Playcount': item['playcount']
    }

    if "showtitle" in item:
        metadata['TVshowTitle'] = item['showtitle']
        label2 = item['showtitle']

    if "episodeid" in item:
        # Listitem of episode
        metadata['mediatype'] = "episode"
        metadata['dbid'] = item['episodeid']

    # TODO: Review once Krypton is RC - probably no longer needed if there's dbid
    if "episode" in item:
        episode = item['episode']
        metadata['Episode'] = episode

    if "season" in item:
        season = item['season']
        metadata['Season'] = season

    if season and episode:
        episodeno = "s%.2de%.2d" % (season, episode)
        li.setProperty('episodeno', episodeno)
        label2 = "%s - %s" % (label2, episodeno) if label2 else episodeno

    if "firstaired" in item:
        metadata['Premiered'] = item['firstaired']

    if "rating" in item:
        metadata['Rating'] = str(round(float(item['rating']),1))

    if "director" in item:
        metadata['Director'] = " / ".join(item['director'])

    if "writer" in item:
        metadata['Writer'] = " / ".join(item['writer'])

    if "cast" in item:
        cast = []
        castandrole = []
        for person in item['cast']:
            name = person['name']
            cast.append(name)
            castandrole.append((name, person['role']))
        metadata['Cast'] = cast
        metadata['CastAndRole'] = castandrole

    li.setLabel2(label2)
    li.setInfo(type="Video", infoLabels=metadata)  
    li.setProperty('resumetime', str(item['resume']['position']))
    li.setProperty('totaltime', str(item['resume']['total']))
    li.setArt(item['art'])
    li.setThumbnailImage(item['art'].get('thumb',''))
    li.setIconImage('DefaultTVShows.png')
    li.setProperty('dbid', str(item['episodeid']))
    li.setProperty('fanart_image', item['art'].get('tvshow.fanart',''))

    for key, value in item['streamdetails'].iteritems():
        for stream in value:
            li.addStreamInfo(key, stream)

    return li

def add_user():

    ''' Add or remove users from the default server session.
    '''
    if not window('emby_online.bool'):
        return

    session = TheVoid('GetSession', {}).get()
    users = TheVoid('GetUsers', {'IsDisabled': False, 'IsHidden': False}).get()
    current = session[0]['AdditionalUsers']

    result = dialog("select", _(33061), [_(33062), _(33063)] if current else [_(33062)])

    if result < 0:
        return

    if not result: # Add user
        eligible = [x for x in users if x['Id'] not in [current_user['UserId'] for current_user in current]]
        resp = dialog("select", _(33064), [x['Name'] for x in eligible])

        if resp < 0:
            return

        user = eligible[resp]
        event('AddUser', {'Id': user['Id'], 'Add': True})
    else: # Remove user
        resp = dialog("select", _(33064), [x['UserName'] for x in current])

        if resp < 0:
            return

        user = current[resp]
        event('AddUser', {'Id': user['UserId'], 'Add': False})

def get_themes():

    ''' Add theme media locally, via strm. This is only for tv tunes.
        If another script is used, adjust this code.
    '''
    from helper.utils import normalize_string
    from helper.playutils import PlayUtils
    from helper.xmls import tvtunes_nfo

    library = xbmc.translatePath("special://profile/addon_data/plugin.video.emby/library/").decode('utf-8')
    play = settings('useDirectPaths') == "1"

    if not xbmcvfs.exists(library):
        xbmcvfs.mkdir(library)

    if xbmc.getCondVisibility('System.HasAddon(script.tvtunes)'):

        tvtunes = xbmcaddon.Addon(id="script.tvtunes")
        tvtunes.setSetting('custom_path_enable', "true")
        tvtunes.setSetting('custom_path', library)
        LOG.info("TV Tunes custom path is enabled and set.")
    else:
        dialog("ok", heading="{emby}", line1=_(33152))

        return

    with Database('emby') as embydb:
        all_views = emby_db.EmbyDatabase(embydb.cursor).get_views()
        views = [x[0] for x in all_views if x[2] in ('movies', 'tvshows', 'mixed')]


    items = {}
    server = TheVoid('GetServerAddress', {'ServerId': None}).get()
    token = TheVoid('GetToken', {'ServerId': None}).get() 

    for view in views:
        result = TheVoid('GetThemes', {'Type': "Video", 'Id': view}).get()

        for item in result['Items']:

            folder = normalize_string(item['Name'].encode('utf-8'))
            items[item['Id']] = folder

        result = TheVoid('GetThemes', {'Type': "Song", 'Id': view}).get()

        for item in result['Items']:

            folder = normalize_string(item['Name'].encode('utf-8'))
            items[item['Id']] = folder

    for item in items:

        nfo_path = os.path.join(library, items[item])
        nfo_file = os.path.join(nfo_path, "tvtunes.nfo")

        if not xbmcvfs.exists(nfo_path):
            xbmcvfs.mkdir(nfo_path)

        themes = TheVoid('GetTheme', {'Id': item}).get()
        paths = []

        for theme in themes['ThemeVideosResult']['Items'] + themes['ThemeSongsResult']['Items']:
            putils = PlayUtils(theme, False, None, server, token)

            if play:
                paths.append(putils.direct_play(theme['MediaSources'][0]).encode('utf-8'))
            else:
                paths.append(putils.direct_url(theme['MediaSources'][0]).encode('utf-8'))

        tvtunes_nfo(nfo_file, paths)

    dialog("notification", heading="{emby}", message=_(33153), icon="{emby}", time=1000, sound=False)

def delete_item():

    ''' Delete keymap action.
    '''
    import context

    context.Context(delete=True)
