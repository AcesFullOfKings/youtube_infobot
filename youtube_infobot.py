import time
import requests
import re
import pickle
import youtube_infobot_info as info

import praw

gBrowserKey  = info.gBrowserKey
app_user_agent = ("Finds youtube links and provides additional information. "
                  "Written, hosted, and operated by /u/theonefoster")
app_ID = info.app_ID
app_secret = info.app_secret
app_URI = info.app_URI
app_refresh_token = info.app_refresh_token

youtube_id_regex = re.compile(
                       "(http(s)?:\/\/)?(www|m).youtube.com\/.*v=([a-zA-Z0-9_-]*)")
                       # group 3 is ID (fourth group, zero-based)
youtube_id_regex_alt = re.compile(
                       "(http(s)?:\/\/)?yo(u)tu.be/([0-9a-zA-z-_]*)")
                       # group 3 is still the ID
time_regex = re.compile(
                       "PT(([0-9]{1,2})H)?(([0-9]{1,2})M)?(([0-9]{1,2})S)") 
                        #group 1 is H, 3 is M, 5 is S

banned_regex = re.compile("you've been banned from /r/.*")

reply_template = """Here is some information about the youtube video you linked to:

Title| {title}
---|---
Channel Name| {channel}
Views| {views}
Length| {length}
Likes| {likes}
Dislikes| {dislikes}
Likes Ratio| {like_ratio}

[^Source]({source}) ^- [^Feedback]({feedback})

"""

yt_dict = []
done_items = []
no_shortlink_subs = info.no_shortlink_subs

with open("banlist.p",'rb') as f:
    banlist = pickle.load(f)

def login():
    print("logging in..")
    r = praw.Reddit(app_user_agent)
    r.set_oauth_app_info(app_ID,app_secret, app_URI)
    r.refresh_access_information(app_refresh_token)
    print("logged in as " + str(r.user.name))
    return r

def getYoutubeVideoData(part, input_type, input_val): 
    # part=where to search, input = search value, val=return value
    # read like "from LOCATION, get the PART where INPUT_TYPE is INPUT_VAL 
    # and return RETURN_VAL
    # where location is channel/video, part is statistics/snippet/status,
    # type is ID or fromUsername, val is the search value, return value is 
    # the data you want

    try:
        global yt_dict
        URL = ("https://www.googleapis.com/youtube/v3/videos?part=" + part 
               + "&" + input_type + "=" + input_val + "&key=" + gBrowserKey)
        response = requests.get(URL).json()
        yt_dict = response['items'][0]
    except:
        return -1

def youtube_info():
    for c in all:
            if c.id not in done_items and c.subreddit.display_name not in banlist:
                done_items.append(c.id)
                match = re.findall(youtube_id_regex, c.body)
                if not match:
                    match = re.findall(youtube_id_regex_alt, c.body)
                if match:
                    if len(match) > 1:
                        #for m in match:
                        #    getYoutubeVideoData("snippet", "id", m[4]) #TODO
                        print("Multiple links in comment. No reply given.")
                    else:
                        getYoutubeVideoData("snippet", "id", match[0][3])
                        snippet = yt_dict['snippet']
                        title = snippet['title'].replace("|","")
                        publishedAt = snippet['publishedAt']
                        channel = snippet['channelTitle']
                        getYoutubeVideoData("statistics", "id", match[0][3])
                        stats = yt_dict['statistics']
                        likes = stats['likeCount']
                        dislikes = stats['dislikeCount']
                        views = stats['viewCount']
                        getYoutubeVideoData("contentDetails", "id", match[0][3])
                        length = yt_dict['contentDetails']['duration']
                        times = re.findall(time_regex, length)[0]
                        hours = times[1]
                        mins = times[3]
                        secs = times[5]
                        duration = ""
                        more_than_a_min = False

                        if hours != '':
                            more_than_a_min = True
                            duration += str(hours) + ":"

                        if more_than_a_min or mins != '':
                            if more_than_a_min and int(mins) < 10:
                                duration += "0" + str(mins) + ":"
                            else:
                                duration += str(mins) + ":"
                            more_than_a_min = True

                        if more_than_a_min and int(secs) < 10:
                                duration += "0" + str(secs)
                        else:
                            duration += str(secs)

                        if not more_than_a_min:
                            duration += " seconds"

                        if int(dislikes) == 0:
                            ratio = "100%"
                        elif int(likes) == 0:
                            ratio = "0%"
                        else:
                            ratio = str(round((int(likes)/(int(likes)+int(dislikes)))*100,1)) + "%"

                        if c.subreddit.display_name.lower() in no_shortlink_subs:
                            source = info.long_source
                            feedback = info.long_feedback
                        else:
                            source = info.short_source
                            feedback = info.short_feedback

                        views = "{:,}".format(int(views))
                        reply = reply_template.format(title=title, channel=channel, likes=likes, 
                                                      dislikes=dislikes, views=views, length=duration, 
                                                      like_ratio=ratio, feedback=feedback, source=source)
                        c.reply(reply)
                        print("Replied to comment " + c.id)

def get_messages():
    unread = r.get_unread()

    for m in unread:
        if m.subject.startswith("you've been banned from /r/"):
            sub = m.subject[27:]
            banlist.append(sub)
            with open("banlist.p", 'wb') as f:
                pickle.dump(banlist,f)
            m.mark_as_read()
            m.reply("Sorry to bother you. I won't reply any more in your subreddit.")
            print("Added ban from /r/" + sub)

r = login()

while True:
    try:
        r.handler.clear_cache()
        all = r.get_subreddit("all")
        all = all.get_comments(limit=100)
        all = list(all)

        youtube_info()
        get_messages()
        
        time.sleep(5)
    except praw.errors.HTTPException as e:
        print("Http Error - " +  str(e))
        time.sleep(60)
    except praw.errors.RateLimitExceeded as e:
        print("Rate limit exceeded! - " + str(e))
        waittime = int(e.message[42:44])
        if e.message[44:].startswith("minutes"):
            unit = "minutes"
        else:
            unit = "seconds"
        
        if unit == "minutes":
            waittime += 1
            waittime *= 60

        print("Waiting " + str(waittime))
        time.sleep(int(waittime))

    except Exception as e:
        print("Error - " + str(e))
        time.sleep(30)
