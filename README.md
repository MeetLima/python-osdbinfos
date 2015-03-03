# About

osdbinfos let you identify a local video file based on its content and the help of the [opensubtitles](http://www.opensubtitles.org/) [API](trac.opensubtitles.org/projects/opensubtitles/wiki/XMLRPC)

This module just provide video file identification; It does not download any subtitle;

# Example usage :

## As a module

    from osdbinfos import OpenSutitles

    path = "Pioneer One/Pioneer.One.S01E01.REDUX.720p.x264-VODO/Pioneer.One.S01E01.REDUX.720p.x264-VODO.mkv"
    osdb = OpenSutitles()
    print(osdb.get_files_infos([path, ]))
    {'Pioneer One/Pioneer.One.S01E01.REDUX.720p.x264-VODO/Pioneer.One.S01E01.REDUX.720p.x264-VODO.mkv': {u'kind': 'episode', u'movie_hash': 'e1c675becea90705', u'serie_title': u'Pioneer One', u'imdb_id': 'tt1834084', u'episode_title': u'Earthfall', u'episode_number': 1, u'season_number': 1}}


    


## From CLI :

    ~: osdbinfos-example "Pioneer One/Pioneer.One.S01E02.720p.x264-VODO/Pioneer.One.S01E02.720p.x264-VODO.mkv" | python -m json.tool
    {
        "Pioneer One/Pioneer.One.S01E02.720p.x264-VODO/Pioneer.One.S01E02.720p.x264-VODO.mkv": {
            "episode_number": 2,
            "episode_title": "The Man from Mars",
            "imdb_id": "tt1835555",
            "kind": "episode",
            "movie_hash": "19b48b9a2f464caa",
            "season_number": 1,
            "serie_title": "Pioneer One"
        }
    }



In this example, files used are the first and second episode of "Pioneer One" freely available on [Vodo.net](http://vodo.net/joshbernhard/pioneerone/)
