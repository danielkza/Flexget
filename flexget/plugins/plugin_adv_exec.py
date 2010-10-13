import subprocess
import logging
import shlex
import pipes
from flexget.plugin import *

log = logging.getLogger('adv_exec')


class PluginAdvExec(object):
    """
    Execute commands

    Example:

    adv_exec:
      on_start:
        event: echo "Started"
      on_input:
        for_entries: echo 'got %(title)s'
      on_output:
        for_accepted: echo 'accepted %(title)s - %(url)s > file

    You can use all (available) entry fields in the command.
    """

    NAME = 'adv_exec'

    def validator(self):
        from flexget import validator
        root = validator.factory('dict')

        def add(name):
            event = root.accept('dict', key=name)
            event.accept('text', key='event')
            event.accept('text', key='for_entries')
            event.accept('text', key='for_accepted')
            event.accept('text', key='for_rejected')
            event.accept('text', key='for_failed')

        for name in ['on_start', 'on_input', 'on_filter', 'on_output', 'on_exit']:
            add(name)

        root.accept('boolean', key='fail_entries')

        return root

    def on_feed_start(self, feed):
        self.execute(feed, 'on_start')

    # Make sure we run after other plugins so exec can use their output
    @priority(100)
    def on_feed_input(self, feed):
        self.execute(feed, 'on_input')

    # Make sure we run after other plugins so exec can use their output
    @priority(100)
    def on_feed_filter(self, feed):
        self.execute(feed, 'on_filter')

    # Make sure we run after other plugins so exec can use their output
    @priority(100)
    def on_feed_output(self, feed):
        self.execute(feed, 'on_output')

    def on_feed_exit(self, feed):
        self.execute(feed, 'on_exit')

    def execute_cmd(self, cmd):
        p = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, \
            stderr=subprocess.STDOUT, close_fds=False)
        (r, w) = (p.stdout, p.stdin)
        response = r.read()
        r.close()
        w.close()
        if response:
            log.info('Stdout: %s' % response)
        return p.wait() 

    def execute(self, feed, event_name):
        if not event_name in feed.config[self.NAME]:
            log.debug('event %s not configured' % event_name)
            return

        name_map = {'for_entries': feed.entries, 'for_accepted': feed.accepted, \
            'for_rejected': feed.rejected, 'for_failed': feed.failed}

        for operation, entries in name_map.iteritems():
            if not operation in feed.config[self.NAME][event_name]:
                continue

            log.debug('running event_name: %s operation: %s entries: %s' % (event_name, operation, len(entries)))

            for entry in entries:
                try:
                    cmd = feed.config[self.NAME][event_name][operation]

                    args = []
                    # shlex is documented to not work on unicode
                    for arg in shlex.split(cmd.encode('utf-8'), comments=True):
                        arg = unicode(arg, 'utf-8')
                        formatted = arg % entry
                        if formatted != arg:
                            arg = pipes.quote(formatted)
                        args.append(arg)
                    cmd = ' '.join(args)

                except KeyError, e:
                    msg = 'Entry %s does not have required field %s' % (entry['title'], e.message)
                    log.error(msg)
                    # fail the entry if configured to do so
                    if feed.config[self.NAME].get('fail_entries'):
                        feed.fail(entry, msg)
                    continue

                log.debug('event_name: %s operation: %s cmd: %s' % (event_name, operation, cmd))
                if feed.manager.options.test:
                    log.info('Would execute: %s' % cmd)
                else:
                    # Run the command, fail entries with non-zero return code if configured to
                    if self.execute_cmd(cmd) != 0 and feed.config[self.NAME].get('fail_entries'):
                        feed.fail(entry, "adv_exec return code was non-zero")

        # event keyword in this
        if 'event' in feed.config[self.NAME][event_name]:
            cmd = feed.config[self.NAME][event_name]['event']
            log.debug('event cmd: %s' % cmd)
            if feed.manager.options.test:
                log.info('Would execute: %s' % cmd)
            else:
                self.execute_cmd(cmd)


register_plugin(PluginAdvExec, 'adv_exec')
