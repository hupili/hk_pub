import csv
import logging

logging.basicConfig(filename='book_record_parser.log',level=logging.WARNING)
logger = logging.getLogger()

DEBUG = True
DASH = '—'
SLASH = '/'

currencies = ('$', 'CNY', 'USD', 'GBP', 'NTD')
serial_prefixes = ('ISSN', 'ISBN')

this_year = 2008

def contains_with_any(s, prefixes):
    for prefix in prefixes:
        if s.startswith(prefix):
            return True
    return False

def is_Chi_char(char):
    return '\u4e00' <= char <= '\u9fff'

def is_encapsulated_in_brackets(s):
    try:
        return (s[0] == '(') and (s[-1] == ')')
    except IndexError:
        return False

def is_description(s):
    common_descriptions = ('附唯讀記憶光碟1隻',
                           '內容以簡體字排版',
                           '中英對照',
                           '中文內容以簡體字排版',
                           '部分內容以英文排版',
                           '附鐳射光碟1隻',
                           )
    common_description_keywords = ('對照',
                                   '附'
                                  )

    for kw in common_description_keywords:
        if kw in s:
            return True
    return s in common_descriptions


def clean_string(seg):
    if not seg:
        return ''

    PERIOD_WHITELIST = ('ed.',
                        'pbk.',
                        'cm.',
                        )

    result = seg.replace('\n', ' ')

    # Delete trailing spaces and periods.

    keep_trailing_symbol = False
    while result and ((result[-1] == ' ') or (result[-1] == '.')):
        for s in PERIOD_WHITELIST:
            if result.endswith(s):
                keep_trailing_symbol = True
        if keep_trailing_symbol:
            break
        else:
            result = result[:-1]

    while result and result[0] == ' ':
        result = result[1:]

    if (len(result) == 5) and result[0] == 'c':
        try:
            int(result[1:])
            result = result[1:]
        except ValueError:
            pass
            # Clean string like "c2008"

    if result and (result[0] == '[') and (result[-1] == ']') and (len(result) == 6):
        try:
            int(result[1:-1])
            result = result[1:-1]
        except ValueError:
            pass
            # Clean string like "[2008]"

    # Delete spaces around Chinese characters
    try:
        for i in range(1, len(result) - 1):
            char, char_before, char_after = result[i], result[i - 1], result[i + 1]
            if char == ' ' and (is_Chi_char(char_before) or is_Chi_char(char_after)):
                result = result[:i] + result[i + 1:]
    except IndexError:
        pass

    if len(result) >= 3:
        if (result[0] == '(') and (result[-1] == ')'):
            result = result[1:-1]

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
                'Vol.',
                )
    for kw in keywords:
        if kw in s:
            return True
    return False

def has_author_info(s):
    keywords = ('著',
                '編',
                '譯',
                )
    for kw in keywords:
        if kw in s:
            return True
    return False


def parse_serial_line(s):
    """
    Parse a string in the form of "ISBN 978-1-4058-6246-2 (pbk.) : Unpriced"
    Return a dictionary, in the form of
    {'ISBN': '978-1-4058-6246-2',
     'type_of_serial': 'ISBN',
     'medium': 'pbk.',
     'price': 'Unpriced',
     'price_currency': '',}
    :param s:
    :return:
    """

    # For lines like $35.00, with no ISBN information
    if s[0] == '$':
        try:
            float(s[1:])
            return {'ISBN': '',
                    'ISSN': '',
                    'type_of_serial': '',
                    'medium': '',
                    'price': s[1:],
                    'price_currency': '$',
                    }
        except ValueError:
            pass

    if 'ISBN' in s:
        type_of_serial = 'ISBN'
    elif 'ISSN' in s:
        type_of_serial = 'ISSN'
    else:
        type_of_serial = ''

    if '(' in s:
        pos_left = s.find('(')
        pos_right = s.find(')')
        medium = s[pos_left+1:pos_right]
        s = s[:pos_left] + ' ' + s[pos_right+1:]
    else:
        medium = ''

    if ('$' not in s) and (':' not in s) and ('CNY' not in s):
        # Only serial number
        return {type_of_serial: s[5:],
                'type_of_serial': s[:4],
                'medium': medium,
                'price': '',
                'price_currency': '',}

    if ':' not in s:
        s = s.replace('  ', ':', 1)
        if ':' not in s:
            s = s.replace(' $', ':$', 1)

    while s.count(':') > 1:
        s = s.replace(':', '', 1)
        # Remove redundant colons, either pre-existing in the PDFs,
        # or generated by the colon-adding operations above.

    serial_part, price_part = s.split(':')
    serial = serial_part.replace(type_of_serial+' ', '')
    for currency in currencies:
        if currency in price_part:
            price = price_part.replace(currency, '')
            price_currency = currency
            break
    else:
        price = price_part
        price_currency = ''

    return {type_of_serial: serial,
            'type_of_serial': type_of_serial,
            'medium': medium,
            'price': price,
            'price_currency': price_currency}


def parse_publication_entry(entry):
    segs = entry.split(DASH)
    is_Chinese_book = len(segs) == 1

    result = {}

    if is_Chinese_book:
        result['language'] = 'Chinese'

        segs = entry.splitlines()

        if (len(segs[-1]) > len('(200x-xxxxx)')) or  ('劃' in segs[-1] and len(segs[-1]) <= 4):
            del segs[-1]  # Garbages from PDF-to-txt conversion.

        # Some times there are two lines of garbages, in the form of
        #     D1876 2009 ...
        #     三劃
        if not is_encapsulated_in_brackets(segs[-1]):
            del segs[-1]

        if DEBUG:
            print(segs)

        id_segment = segs[-1]
        result['serial'] = id_segment[1:-1]

        double_ISBN = entry.count('ISBN ') == 2
        double_ISSN = entry.count('ISSN ') == 2

        if contains_with_any(segs[-2], serial_prefixes):
            serial_segment = segs[-2]
            info = parse_serial_line(serial_segment)

            type_of_serial = info['type_of_serial']
            result[type_of_serial+'_1'] = info[type_of_serial]

            result['medium_1'] = info['medium']
            result['price_1'] = info['price']
            result['price_1_currency'] = info['price_currency']

            if double_ISBN or double_ISSN:
                serial_segment = segs[-3]
                info = parse_serial_line(serial_segment)

                type_of_serial = info['type_of_serial']
                result[type_of_serial+'_1'] = info[type_of_serial]

                result['medium_2'] = info['medium']
                result['price_2'] = info['price']
                result['price_2_currency'] = info['price_currency']
                del segs[-3]

        else:
            segs.insert(-1, 'Serial filler row')

        if (")" in segs[-3]) and not ('(' in segs[-3]):
            # Second line of a two-line stories
            segs[-3] = segs[-4].replace('\n', '') + segs[-3]
            del segs[-4]

        if (is_description(segs[-3])) or (is_encapsulated_in_brackets(segs[-3])):
            result['details'] = segs[-3]
            del segs[-3]
        else:
            result['format'] = segs[-3]

        if str(this_year) not in segs[-4]:
            publisher_segment = segs[-3] + segs[-4]
            del segs[-4]
        else:
            publisher_segment = segs[-4]

        year, location, publisher = publisher_segment.split(' ', maxsplit=2)
        if '修訂二版' in publisher:
            result['details'] += '修訂二版'
            publisher = publisher.replace('修訂二版', '')
        result['year_of_publication'] = year
        result['location_of_publication'] = location
        result['publisher'] = publisher

    else:

        result['language'] = 'English'

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

        id_marker = '(2008'
        ISBN_marker = 'ISBN'
        if ISBN_marker in segs[2]:
            format_segment = segs[2][:segs[2].find(ISBN_marker)]
            reminder = segs[2][segs[2].find(ISBN_marker):]
            serial_segment = reminder[:reminder.find(id_marker)]
            id_segment = reminder[reminder.find(id_marker):]
        else:  # No ISBN
            serial_segment = ''
            format_segment =segs[2][:segs[2].find(id_marker)]
            id_segment = segs[2][segs[2].find(id_marker):]

        if serial_segment.count('ISBN') == 2:
            pos_ISBN_1 = serial_segment.find('ISBN')
            pos_lineend_1 = serial_segment.find('\n', pos_ISBN_1)
            pos_ISBN_2 = serial_segment.find('ISBN', pos_ISBN_1+1)
            pos_lineend_2 = serial_segment.find('\n', pos_ISBN_2)
            info1 = parse_serial_line(serial_segment[pos_ISBN_1:pos_lineend_1])
            info2 = parse_serial_line(serial_segment[pos_ISBN_2:pos_lineend_2])

            result['ISBN_1'] = info1['ISBN']
            result['medium_1'] = info1['medium']
            result['price_1'] = info1['price']
            result['price_1_currency'] = info1['price_currency']

            result['ISBN_2'] = info2['ISBN']
            result['medium_2'] = info2['medium']
            result['price_2'] = info2['price']
            result['price_2_currency'] = info1['price_currency']

        elif serial_segment.count('ISBN') == 1:
            serial_segment = clean_string(serial_segment)
            info = parse_serial_line(serial_segment)
            result['ISBN_1'] = info['ISBN']
            result['medium_1'] = info['medium']
            result['price_1'] = info['price']
            result['price_1_currency'] = info['price_currency']

        if (len(id_segment) > len('(xxxx-yyyyy)\n')) and ('\n' in id_segment):
            id_segment = id_segment.split('\n', maxsplit=1)[0]
            # Remove garbage from PDF headers

        if 'cm.' in format_segment:
            format_segment, detail_info = format_segment.split('cm.', maxsplit=1)
            format_segment = format_segment + 'cm.'

        else:
            detail_info = ''

        result['format'] = format_segment

        result['serial'] = id_segment

        result['details'] = detail_info

    for key in result:
        result[key] = clean_string(result[key])

    if DEBUG:
        for key in result:
            print(key + '=' + result[key])
        print('\n')

    if not DEBUG:
        result['original_record'] = entry

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
        lower = 1191
        upper = 1191

    begin, end = 0, 0
    for rank in range(lower, upper + 1):
        print('rank=',rank)
        begin = txt.find(str(rank) + '\n', end)
        end = txt.find(str(rank + 1) + '\n', begin)
        offset = len(str(rank))
        entry_in_txt = txt[begin+1 + offset:end]

        try:
            record = parse_publication_entry(entry_in_txt)
            records.append(record)
        except ValueError as error:
            logger.warn('Failed to parse:\n'+entry_in_txt)
            logger.info(str(error))


    prefix = ''
    if DEBUG:
        import random

        prefix = 'debug' + str(random.randint(1, 1000)) + '_'

    with open(prefix + '2008.csv', 'w', newline='') as csvfile:
        fieldnames = ['serial',
                      'title_eng',
                      'title_chi',
                      'language',
                      'author',
                      'detailed_authorship',
                      'publisher',
                      'ISBN_1',
                      'ISSN_1',
                      'medium_1',
                      'price_1_currency',
                      'price_1',
                      'ISBN_2',
                      'ISSN_2',
                      'medium_2',
                      'price_2_currency',
                      'price_2',
                      'location_of_publication',
                      'year_of_publication',
                      'format',
                      'details',
                      'original_record',
                      'edition',
                      ]
        writer = csv.DictWriter(csvfile, dialect='excel', fieldnames=fieldnames)
        writer.writeheader()

        for record in records:
            writer.writerow(record)
