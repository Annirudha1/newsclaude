from django.db import migrations


def normalize_upload_playlist_ids(apps, schema_editor):
    YouTubeChannel = apps.get_model('news', 'YouTubeChannel')
    for channel in YouTubeChannel.objects.filter(channel_id__startswith='UU'):
        channel.channel_id = f'UC{channel.channel_id[2:]}'
        channel.save(update_fields=['channel_id'])


class Migration(migrations.Migration):
    dependencies = [('news', '0004_youtubechannel_short')]

    operations = [migrations.RunPython(normalize_upload_playlist_ids, migrations.RunPython.noop)]
