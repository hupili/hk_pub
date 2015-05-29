import csv

DEBUG = True
DASH = '—'
SLASH = '/'


def is_Chi_char(char):
    return '\u4e00' <= char <= '\u9fff'


def clean_string(seg):
    if not seg:
        return ''

    result = seg.replace('\n', ' ')

    while (result[-1] == ' ') or (result[-1] == '.'):
        try:
            if result[-3:] == 'ed.':
                break
        except IndexError:
            pass
        result = result[:-1]

    while result[0] == ' ':
        result = result[1:]

    if (len(result) == 5) and result[0] == 'c':
        try:
            int(result[1:])
            result = result[1:]
        except ValueError:
            pass
            # Clean string like "c2008"

    if (result[0] == '[') and (result[-1] == ']') and (len(result) == 6):
        try:
            int(result[1:-1])
            result = result[1:-1]
        except ValueError:
            pass
            # Clean string like "[2008]"

    try:
        for i in range(1, len(result) - 1):
            char, char_before, char_after = result[i], result[i - 1], result[i + 1]
            if char == ' ' and is_Chi_char(char_before) and is_Chi_char(char_after):
                result = result[:i] + result[i + 1:]
    except IndexError:
        pass

    return result


def is_author_name(s):
    """
    Check if s is in the form of "ANNELLS, Deborah"
    :param s:
    :return:
    """
    if ',' not in s:
        return False
    seg1, seg2 = s.split(',', maxsplit=1)
    seg2 = seg2[1:]  # Delete the space
    if seg1.isupper() and seg2[0].isupper() and seg2[1:].islower():
        return True
        # TODO: False negative with names like "HOWARD, Leslie R."
    return False


def has_detailed_edition_info(s):
    keywords = ('ed.',
                'reissue',
                'Issue',
                'edition',
                '12.2007',
                'version',
                'Vol.'
                )
    for kw in keywords:
        if kw in s:
            return True
    return False


def parse_publication_entry(entry):
    segs = entry.split(DASH)
    is_Chinese_book = len(segs) == 1

    result = {}

    if is_Chinese_book:
        pass  # TODO

    else:  # English publication

        title_segment = segs[0]
        if title_segment[0] == '\n':
            title_segment = title_segment[1:]

        first_line = title_segment.split('\n', maxsplit=1)[0]
        if is_author_name(first_line):
            result['author'] = first_line
            title_segment = title_segment.split('\n', maxsplit=1)[1]

        if SLASH in title_segment:
            if 'by' in title_segment:
                result['detailed_authorship'] = title_segment.rsplit(SLASH, maxsplit=1)[1]
                title_segment = title_segment.rsplit(SLASH, maxsplit=1)[0]
            else:
                title_segment, result['author'] = title_segment.rsplit(SLASH, maxsplit=1)

        if has_detailed_edition_info(segs[1]):
            # This book is not the first edition, and the second segment is just
            # "2nd ed.' or 'New ed.', et cetera.
            result['edition'] = clean_string(segs[1])
            segs[1:-1] = segs[2:-1]
            del segs[-1]

        if '=' in title_segment:
            # bilingual title
            result['title_eng'] = title_segment.split('=')[0]
            result['title_chi'] = title_segment.split('=')[1]
        else:
            result['title_eng'] = title_segment

        publisher_segment = segs[1]
        s1, s2 = publisher_segment.split(':', maxsplit=1)
        s2, s3 = s2.rsplit(',', maxsplit=1)
        result['location_of_publication'] = s1
        result['publisher'] = s2
        result['year_of_publication'] = s3

        ISBN_marker = 'ISBN'
        serial_marker = '(2008'
        publishing_segment = segs[2][:segs[2].find(ISBN_marker)]
        reminder = segs[2][segs[2].find(ISBN_marker):]
        ISBN_segment = reminder[:reminder.find(serial_marker)]
        serial_segment = reminder[reminder.find(serial_marker):]
        print('=======\n')
        print(publishing_segment, ISBN_segment, serial_segment)
        print('=======\n')

    for key in result:
        result[key] = clean_string(result[key])

    if DEBUG:
        for key in result:
            print(key + '=' + result[key])
        print('\n')

    return result


if __name__ == '__main__':

    source_url = 'txt/2008_txt'
    f = open(source_url)
    txt = f.read()

    # Cleaning
    txt = txt.replace('1 =', '=')
    txt = txt.replace('1 —', '—')

    records = []

    lower = 1
    upper = 2818
    if DEBUG:
        lower = 1
        upper = 1000

    begin, end = 0, 0
    for rank in range(lower, upper + 1):
        begin = txt.find(str(rank) + '\n', end)
        end = txt.find(str(rank + 1) + '\n', begin)
        offset = len(str(rank))
        entry_in_txt = txt[begin + offset:end]

        try:
            record = parse_publication_entry(entry_in_txt)
        except (IndexError, ValueError):
            record = {'original_record': entry_in_txt}
        records.append(record)

    prefix = ''
    if DEBUG:
        import random

        prefix = 'debug' + str(random.randint(1, 1000)) + '_'

    with open(prefix + '2008.csv', 'w', newline='') as csvfile:
        fieldnames = ['title_chi',
                      'title_eng',
                      'author',
                      'detailed_authorship',
                      'publisher',
                      'ISBN',
                      'ISBN_audio',
                      'price',
                      'price_audio',
                      'location_of_publication',
                      'year_of_publication',
                      'format',
                      'details',
                      'original_record',
                      'serial',
                      'edition',
                      ]
        writer = csv.DictWriter(csvfile, dialect='excel', fieldnames=fieldnames)
        writer.writeheader()

        for record in records:
            writer.writerow(record)
