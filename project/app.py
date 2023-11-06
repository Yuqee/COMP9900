from flask import Flask, render_template, g, request, session, redirect, url_for, flash
from flask_mail import Mail, Message
from database import get_db
from werkzeug.security import generate_password_hash, check_password_hash
import os
import re
from datetime import datetime
import base64

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

senderName = "COMP9900H16ASUN"

def send_email(senderName, title, message, recipients=None, bcc=None):
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Server address
    app.config['MAIL_PORT'] = 465  # Server port number
    app.config['MAIL_USE_TLS'] = False  # Encryption method: not TLS
    app.config['MAIL_USE_SSL'] = True  # Encryption method: SSL
    app.config['MAIL_USERNAME'] = 'COMP9900H16ASUN@gmail.com'  # Address of our offical email
    app.config['MAIL_PASSWORD'] = 'flwjakacaqjpqeob'  # The Authentication passcode of our offical email: COMP9900H16ASUN@gmail.com
    mail = Mail(app)

    with app.app_context():
        msg = Message(title,sender=(senderName,app.config['MAIL_USERNAME']), recipients=recipients, bcc=bcc)
        msg.html = message
        mail.send(msg)

def group_email_address(id, to_list):
    '''
    id is event_id
    to_list stores types of users: 0 or 1 or 2
    0: wishlist costomers, 1: ticket buying costomers, 2: wishlist exclude valid ticket holders       
    '''
    db = get_db()
    email_recipients_list=[]

    if to_list==0:
        email_recipients_curr = db.execute('''
            SELECT u.email
            FROM Users u
            INNER JOIN Wishlist w ON u.id = w.userId
            WHERE w.eventId = ?
        ''', [id])
        email_recipients = email_recipients_curr.fetchall()
        email_recipients_list = list(set(email['email'] for email in email_recipients))

    if to_list==1:
        email_recipients_curr = db.execute('''
        select u.email 
        from Events e, SoldTickets st, Users u 
        where e.id = st.forEvent and st.soldTo = u.id and st.status = 'v' and e.id = ?''', [id])
        email_recipients = email_recipients_curr.fetchall()
        email_recipients_list = list(set(email['email'] for email in email_recipients))
    
    if to_list==2:
        email_recipients_curr = db.execute('''
        select u.email from Users u, Wishlist w 
        where u.id = w.userId and w.eventId = ? and w.userId not in (
            select DISTINCT st.soldTo 
            from SoldTickets st 
            where st.forEvent = w.eventId and st.status = "v" )''', [id])
        email_recipients = email_recipients_curr.fetchall()
        email_recipients_list = list(set(email['email'] for email in email_recipients))

    #List of emails of recipients   
    return email_recipients_list

def get_current_user():
    ''' return the information of current user. None for non-login user.'''
    user_result = None
    if 'emailaddress' in session:
        email = session['emailaddress']
        db = get_db()
        user_cur = db.execute('select id, name, email, password, is_host from Users where email = ?', [
            email
        ])
        user_result = user_cur.fetchone()
    return user_result

@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    user = get_current_user()
    db = get_db()

    # 3 generic queries for index.html page

    # 1. extract all events with start date time after current date time.
    event_cur = db.execute('''
    select e.*, u.name as host, min(p.price) as min_price
    from Events e, Users u, Price p
    where e.hostedBy = u.id and (e.startDate || ' ' || e.startTime) > datetime('now') and e.status = "v" and p.forEvent=e.id and p.status="v" 
    group by e.id''')

    # 2. fire sale events with start date time after current date time.
    event_sale_cur = db.execute('''
    select e.*, u.name as host, min(p.price) as min_price
    from Events e, Users u, Price p
    where e.hostedBy = u.id and (e.startDate || ' ' || e.startTime) > datetime('now') and e.status = "v" and p.forEvent=e.id and p.status="v" 
	and e.id in (select distinct forEvent from price where status = 'v' and fireSales = true)
    group by e.id''')

    # 3. non sale events with start date time after current date time.
    event_non_sale_cur = db.execute('''
    select e.*, u.name as host, min(p.price) as min_price
    from Events e, Users u, Price p
    where e.hostedBy = u.id and (e.startDate || ' ' || e.startTime) > datetime('now') and e.status = "v" and p.forEvent=e.id and p.status="v" 
	and e.id not in (select distinct forEvent from price where status = 'v' and fireSales = true)
    group by e.id''')

    # special event lists for host.
    # only show events that are created by the host.
    # separate the events into 3 categories, past events , cancelled events and upcoming events.
    past_events_result = []
    cancelled_events_result = []
    upcoming_events_result = []

    # prospective customer can only see the upcoming events that has tickets available and will be started in a month
    if 'emailaddress' not in session:
        # update the queries for the 3 generic queries.

        event_cur = db.execute('''
        select e.*, u.name as host, l.row*l.column - count(st.id) as sold_num, min(p.price) min_price
        from Events e
        left join SoldTickets st on e.id = st.forEvent and st.status = "v",
        Users u, Layouts l, Price p
        where (e.startDate || ' ' || e.startTime) > datetime('now') and e.startDate <= Date("now", "+30 days") and e.status = "v" and e.layoutId = l.id and e.hostedBy = u.id and p.forEvent = e.id and p.status = 'v'
        group by e.id
        having sold_num >0 ''')

        event_sale_cur = db.execute('''
        select e.*, u.name as host, l.row*l.column - count(st.id) as sold_num, min(p.price) min_price
        from Events e
        left join SoldTickets st on e.id = st.forEvent and st.status = "v",
        Users u, Layouts l, Price p
        where (e.startDate || ' ' || e.startTime) > datetime('now') and e.startDate <= Date("now", "+30 days") and e.status = "v" and e.layoutId = l.id and e.hostedBy = u.id and p.forEvent = e.id and p.status = 'v'
		and e.id in (select distinct forEvent from price where status = 'v' and fireSales = true)
        group by e.id
        having sold_num >0 ''')

        event_non_sale_cur = db.execute('''
        select e.*, u.name as host, l.row*l.column - count(st.id) as sold_num, min(p.price) min_price
        from Events e
        left join SoldTickets st on e.id = st.forEvent and st.status = "v",
        Users u, Layouts l, Price p
        where (e.startDate || ' ' || e.startTime) > datetime('now') and e.startDate <= Date("now", "+30 days") and e.status = "v" and e.layoutId = l.id and e.hostedBy = u.id and p.forEvent = e.id and p.status = 'v'
		and e.id not in (select distinct forEvent from price where status = 'v' and fireSales = true)
        group by e.id
        having sold_num >0 ''')
    
    else:
        # special handling for host
        if user['is_host'] :
            # retrive all events created by the host
            event_cur = db.execute('''
            select e.*, u.name as host, min(p.price) as min_price
            from Events e, Users u, Price p
            where e.hostedBy = u.id and u.id = ? and p.forEvent = e.id and p.status = "v" 
            group by e.id
            order by e.startDate''', [user['id']])

            # upcoming events created by the host
            event_upcoming = db.execute('''
            select e.*, u.name as host, min(p.price) as min_price
            from Events e, Users u, Price p
            where e.hostedBy = u.id and (e.startDate || ' ' || e.startTime) > datetime('now') and e.status='v' and u.id = ? and p.forEvent = e.id and p.status = "v" 
            group by e.id
            order by e.startDate''', [user['id']])

            # past events created by the host
            events_past = db.execute('''
            select e.*, u.name as host, min(p.price) as min_price 
            from Events e, Users u, Price p
            where e.hostedBy = u.id and (e.startDate || ' ' || e.startTime) <= datetime('now') and e.status = "v" and u.id = ? and p.forEvent = e.id and p.status = "v" 
            group by e.id
            order by e.startDate''', [user['id']])

            # cancelled events created by the host
            events_cancelled = db.execute('''
            select e.*, u.name as host, min(p.price) as min_price 
            from Events e, Users u, Price p
            where e.hostedBy = u.id and e.status = 'c' and  u.id = ? and p.forEvent = e.id and p.status = "v" 
            group by e.id
            order by e.startDate''', [user['id']])
            
            upcoming_events_result = event_upcoming.fetchall()
            past_events_result = events_past.fetchall()
            cancelled_events_result = events_cancelled.fetchall()

    if request.method == 'GET':
        pass

    # handling for search function
    if request.method == 'POST' and 'emailaddress' in session and 'search_type' in request.form:
        search_type = request.form.get('search_type')
        search_keyword = request.form.get('search_keyword')
        
        # search on 'title'
        if search_type == 'title':
            
            event_cur = db.execute('''
                SELECT e.*, u.name AS host, min(p.price) as min_price
                FROM Events e, Users u, Price p
                WHERE e.hostedBy = u.id AND LOWER(e.title) LIKE ? and p.forEvent = e.id and p.status = "v" 
                group by e.id
            ''', ('%' + search_keyword.lower() + '%',))

            event_sale_cur = db.execute('''
                SELECT e.*, u.name AS host, min(p.price) as min_price
                FROM Events e, Users u, Price p
                WHERE e.hostedBy = u.id and (e.startDate || ' ' || e.startTime) > datetime('now') AND LOWER(e.title) LIKE ? and p.forEvent = e.id and p.status = "v" 
                and e.id in (select distinct forEvent from price where status = 'v' and fireSales = true)
                group by e.id
            ''', ('%' + search_keyword.lower() + '%',))

            event_non_sale_cur = db.execute('''
                SELECT e.*, u.name AS host, min(p.price) as min_price
                FROM Events e, Users u, Price p
                WHERE e.hostedBy = u.id and (e.startDate || ' ' || e.startTime) > datetime('now') AND LOWER(e.title) LIKE ? and p.forEvent = e.id and p.status = "v" 
                and e.id not in (select distinct forEvent from price where status = 'v' and fireSales = true)
                group by e.id
            ''', ('%' + search_keyword.lower() + '%',))

            # special handling for host
            if user['is_host'] :
                event_cur = db.execute('''
                SELECT e.*, u.name AS host, min(p.price) as min_price
                FROM Events e, Users u, Price p
                WHERE e.hostedBy = u.id AND LOWER(e.title) LIKE ? and u.id = ? and p.forEvent = e.id and p.status = "v" 
                group by e.id
                order by e.startDate
                ''', ['%' + search_keyword.lower() + '%',user['id']])

                event_upcoming = db.execute('''
                SELECT e.*, u.name AS host, min(p.price) as min_price
                FROM Events e, Users u, Price p
                WHERE e.hostedBy = u.id AND LOWER(e.title) LIKE ? and u.id = ? and (e.startDate || ' ' || e.startTime) > datetime('now')  and e.status='v' and p.forEvent = e.id and p.status = "v" 
                group by e.id
                order by e.startDate
                ''', ['%' + search_keyword.lower() + '%',user['id']])

                events_past = db.execute('''
                SELECT e.*, u.name AS host, min(p.price) as min_price
                FROM Events e, Users u, Price p
                WHERE e.hostedBy = u.id AND LOWER(e.title) LIKE ? and u.id = ? and (e.startDate || ' ' || e.startTime) <= datetime('now')  and e.status='v' and p.forEvent = e.id and p.status = "v" 
                group by e.id
                order by e.startDate
                ''', ['%' + search_keyword.lower() + '%',user['id']])

                events_cancelled = db.execute('''
                SELECT e.*, u.name AS host, min(p.price) as min_price
                FROM Events e, Users u, Price p
                WHERE e.hostedBy = u.id AND LOWER(e.title) LIKE ? and u.id = ? and e.status = 'c' and p.forEvent = e.id and p.status = "v" 
                group by e.id
                order by e.startDate
                ''', ['%' + search_keyword.lower() + '%',user['id']])

                upcoming_events_result = event_upcoming.fetchall()
                past_events_result = events_past.fetchall()
                cancelled_events_result = events_cancelled.fetchall()
            
        # search on start date of the event
        elif search_type == 'startDate':
            # check for invalid or empty input startDate
            try:
                search_date = datetime.strptime(search_keyword, '%Y-%m-%d').date()
                event_cur = db.execute('''
                    SELECT e.*, u.name AS host, min(p.price) as min_price
                    FROM Events e, Users u, Price p
                    WHERE e.hostedBy = u.id AND e.startDate = ? and p.forEvent = e.id and p.status = "v" 
                    group by e.id
                ''', (search_date,))

                event_sale_cur = db.execute('''
                    SELECT e.*, u.name AS host, min(p.price) as min_price
                    FROM Events e, Users u, Price p
                    WHERE e.hostedBy = u.id AND e.startDate = ? and p.forEvent = e.id and p.status = "v" 
                    and (e.startDate || ' ' || e.startTime) > datetime('now') 
                    and e.id in (select distinct forEvent from price where status = 'v' and fireSales = true)
                    group by e.id
                ''', (search_date,))

                event_non_sale_cur = db.execute('''
                    SELECT e.*, u.name AS host, min(p.price) as min_price
                    FROM Events e, Users u, Price p
                    WHERE e.hostedBy = u.id AND e.startDate = ? and p.forEvent = e.id and p.status = "v" 
                    and (e.startDate || ' ' || e.startTime) > datetime('now') 
                    and e.id not in (select distinct forEvent from price where status = 'v' and fireSales = true)
                    group by e.id
                ''', (search_date,))
            except ValueError:
                return redirect(url_for('index'))
            
            # special handling for host
            if user['is_host'] :
                event_cur = db.execute('''
                SELECT e.*, u.name AS host, min(p.price) as min_price
                FROM Events e, Users u, Price p
                WHERE e.hostedBy = u.id AND e.startDate = ? and u.id = ? and p.forEvent = e.id and p.status = "v" 
                group by e.id
                order by e.startDate
                ''', [search_date, user['id']])

                event_upcoming = db.execute('''
                SELECT e.*, u.name AS host, min(p.price) as min_price
                FROM Events e, Users u, Price p
                WHERE e.hostedBy = u.id AND e.startDate = ? and u.id = ? and (e.startDate || ' ' || e.startTime) > datetime('now')  and e.status='v' and p.forEvent = e.id and p.status = "v" 
                group by e.id
                order by e.startDate
                ''', [search_date, user['id']])

                events_past = db.execute('''
                SELECT e.*, u.name AS host, min(p.price) as min_price
                FROM Events e, Users u, Price p
                WHERE e.hostedBy = u.id AND e.startDate = ? and u.id = ? and (e.startDate || ' ' || e.startTime) <= datetime('now')  and e.status='v' and p.forEvent = e.id and p.status = "v" 
                group by e.id
                order by e.startDate
                ''', [search_date, user['id']])

                events_cancelled = db.execute('''
                SELECT e.*, u.name AS host, min(p.price) as min_price
                FROM Events e, Users u, Price p
                WHERE e.hostedBy = u.id AND e.startDate = ? and u.id = ? and e.status = 'c' and p.forEvent = e.id and p.status = "v" 
                group by e.id
                order by e.startDate
                ''', [search_date, user['id']])

                upcoming_events_result = event_upcoming.fetchall()
                past_events_result = events_past.fetchall()
                cancelled_events_result = events_cancelled.fetchall()

        # search on 'location'
        elif search_type == 'location':
            event_cur = db.execute('''
                SELECT e.*, u.name AS host, min(p.price) as min_price
                FROM Events e, Users u, Price p
                WHERE e.hostedBy = u.id AND LOWER(e.location) LIKE ? and p.forEvent = e.id and p.status = "v" 
                group by e.id
            ''', ('%' + search_keyword.lower() + '%',))

            event_sale_cur = db.execute('''
                SELECT e.*, u.name AS host, min(p.price) as min_price
                FROM Events e, Users u, Price p
                WHERE e.hostedBy = u.id AND LOWER(e.location) LIKE ? and p.forEvent = e.id and p.status = "v" 
                and (e.startDate || ' ' || e.startTime) > datetime('now') 
                and e.id in (select distinct forEvent from price where status = 'v' and fireSales = true)
                group by e.id
            ''', ('%' + search_keyword.lower() + '%',))

            event_non_sale_cur = db.execute('''
                SELECT e.*, u.name AS host, min(p.price) as min_price
                FROM Events e, Users u, Price p
                WHERE e.hostedBy = u.id AND LOWER(e.location) LIKE ? and p.forEvent = e.id and p.status = "v" 
                and (e.startDate || ' ' || e.startTime) > datetime('now') 
                and e.id not in (select distinct forEvent from price where status = 'v' and fireSales = true)
                group by e.id
            ''', ('%' + search_keyword.lower() + '%',))

            # special handling for host
            if user['is_host'] :
                event_cur = db.execute('''
                SELECT e.*, u.name AS host, min(p.price) as min_price
                FROM Events e, Users u, Price p
                WHERE e.hostedBy = u.id AND LOWER(e.location) LIKE ? and u.id = ? and p.forEvent = e.id and p.status = "v" 
                group by e.id
                order by e.startDate
                ''', ['%' + search_keyword.lower() + '%',user['id']])

                event_upcoming = db.execute('''
                SELECT e.*, u.name AS host, min(p.price) as min_price
                FROM Events e, Users u, Price p
                WHERE e.hostedBy = u.id AND LOWER(e.location) LIKE ? and u.id = ? and (e.startDate || ' ' || e.startTime) > datetime('now')  and e.status='v' and p.forEvent = e.id and p.status = "v" 
                group by e.id
                order by e.startDate
                ''', ['%' + search_keyword.lower() + '%',user['id']])

                events_past = db.execute('''
                SELECT e.*, u.name AS host, min(p.price) as min_price
                FROM Events e, Users u, Price p
                WHERE e.hostedBy = u.id AND LOWER(e.location) LIKE ? and u.id = ? and (e.startDate || ' ' || e.startTime) <= datetime('now')  and e.status='v' and p.forEvent = e.id and p.status = "v" 
                group by e.id
                order by e.startDate
                ''', ['%' + search_keyword.lower() + '%',user['id']])

                events_cancelled = db.execute('''
                SELECT e.*, u.name AS host, min(p.price) as min_price
                FROM Events e, Users u, Price p
                WHERE e.hostedBy = u.id AND LOWER(e.location) LIKE ? and u.id = ? and e.status = 'c' and p.forEvent = e.id and p.status = "v" 
                group by e.id
                order by e.startDate
                ''', ['%' + search_keyword.lower() + '%',user['id']])

                upcoming_events_result = event_upcoming.fetchall()
                past_events_result = events_past.fetchall()
                cancelled_events_result = events_cancelled.fetchall()
            
    events_results = event_cur.fetchall()
    events_sale_results = event_sale_cur.fetchall()
    events_non_sale_results = event_non_sale_cur.fetchall()
    
    # decode the poster attribute stored in the database for all events
    base64_imgs = dict()
    for e in events_results:
        base64_imgs[e['id']] = base64.b64encode(e['poster']).decode('utf-8')
        
    # wishlist handling
    if user == None:
        wishlist_result = None
    else:
        wishlist_result=dict()
        for e in events_results:
            wishlist_cur = db.execute('select w.* from Wishlist w where userId = ? and eventId = ?',[user['id'],e['id']])
            wishlist_res = wishlist_cur.fetchone()
            #wishlist_result.append(wishlist_res)
            wishlist_result[e['id']] = wishlist_res
    # add a new event to wishlist
    if request.method == 'POST' and "addwishlist" in request.form:
        db.execute('insert into Wishlist(userId, eventId) values(?,?)',[user['id'],int(request.form['addwishlist'])]) 
        db.commit()
        return redirect(url_for('index'))  
    # remove event in wishlist
    if request.method == 'POST' and 'removewishlist' in request.form:
        db.execute('delete from Wishlist where userId=? and eventId =?',[user['id'],int(request.form['removewishlist'])])
        db.commit()
        return redirect(url_for('index'))

    return render_template('index.html', user=user, events=events_results, imgs = base64_imgs, wishlist=wishlist_result, 
        past_events=past_events_result, cancelled_events = cancelled_events_result, upcoming_events = upcoming_events_result, 
        sale_events = events_sale_results, non_sale_events = events_non_sale_results)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        db = get_db()
        email = request.form['email']
        password = request.form['password']
        #check if email is empty
        if email == "":
            flash("Please enter your email address")
        else:
            #check if email is exist in our database
            email_cur = db.execute('select email from Users where email = ?',[email])
            email_duplicate = email_cur.fetchone()
            if email_duplicate == None:
                flash("This email is not register yet, please register",'error')
            else: 
                user_cur = db.execute('select id, name, email, password, is_host from Users where email = ?', [
                email
                ])
                user_result = user_cur.fetchone()
                # check password
                # all passwords are encrypted even during the checking process -> no password leakage
                if check_password_hash(user_result['password'], password):
                    session['emailaddress'] = user_result['email']
                    session['is_host'] = user_result['is_host']
                    return redirect(url_for('index'))
                else:
                    flash("The password is NOT correct. Please try again.",'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        db = get_db()
        password = request.form['password']
        if request.form['username'] == "":
            flash('Please enter your username','error')
        elif request.form['username'] != "":
            # username must be unique
            name_cur = db.execute('select name from Users where name = ?',[request.form['username']])
            name_duplicate = name_cur.fetchone()
            if name_duplicate != None:
                flash('This name already been registed, please use another name','error')
            elif request.form['email'] == "":
                flash('Please enter your email','error')
            elif request.form['email'] != "":
                # email must be unique
                email_cur = db.execute('select email from Users where email = ?',[request.form['email']])
                email_duplicate = email_cur.fetchone()
                if email_duplicate != None:
                    flash('This email already been registed, please login','error')
                elif password == "":
                    flash('Please enter your password','error')
                
                # check for password requirements
                elif len(password) < 8:
                    flash('Your password must be at least 8 characters','error')
                elif not re.search("[A-Z]", password) or not re.search("[0-9]", password) or not re.search("[a-z]", password):
                    flash('Your password must have at least 1 capital letter, 1 small letter and 1 number','error')
                elif request.form['retypePassword'] == "":
                    flash('Please retype your password','error')
                elif password != request.form['retypePassword']:
                    flash('Your password and retype password is unmatch','error')
                else:
                    user_type = request.form.get('type')
                    # encrypt the password
                    hashed_password = generate_password_hash(request.form['password'], method='sha256')
                    if user_type == 'host':
                        db.execute('insert into Users (email, name, password, is_host) values (?, ?, ?, ?)',[
                            request.form['email'],
                            request.form['username'],
                            hashed_password,
                            True
                        ])
                        db.commit() 
                        session['emailaddress'] = request.form['email']
                        session['is_host'] = True
                        return redirect(url_for('index'))
                    elif user_type == 'user':
                        db.execute('insert into Users (email, name, password, is_host) values (?, ?, ?, ?)',[
                            request.form['email'],
                            request.form['username'],
                            hashed_password,
                            False
                        ])
                        db.commit()
                        session['emailaddress'] = request.form['email']
                        session['is_host'] = False
                        return redirect(url_for('index'))
                    flash('Please choose an user type','error')
    return render_template('register.html')

@app.route('/addevents', methods=['GET', 'POST'])
def addevents():
    ''' function to add new event to the database '''
    user = get_current_user()
    db = get_db()
    current_datetime = datetime.now()
    if request.method == 'POST':
        # check valid inputs for different attributes of an event.    
        if request.form['title'] == "":            
            flash('Please enter the event title','error')
        elif request.form['start_datetime'] == "":
            flash('Please choose a start Date&Time','error')
        elif request.form['end_datetime'] == "":
            flash('Please choose an end Date&Time','error')
        elif datetime.strptime(request.form['start_datetime'], "%Y-%m-%dT%H:%M") < current_datetime:
            flash('Start datetime cannot be a past one!','error')
        elif datetime.strptime(request.form['end_datetime'], "%Y-%m-%dT%H:%M") < datetime.strptime(request.form['start_datetime'], "%Y-%m-%dT%H:%M"):
            flash('The end datetime cannot be earlier than the start datetime!','error')            
        elif request.form['location'] == "":
            flash('Please choose a location','error')  
        # elif request.form.get('poster') == "":
        elif str(request.files.get('poster'))=="<FileStorage: '' ('application/octet-stream')>":
            flash('Please choose a poster','error')  
        else:
            layout_choice = int(request.form.get('layoutChoice'))
            zone_cur = db.execute('''select id, startRow, endRow, layoutId from Zones
                                  where layoutId={}'''.format(layout_choice))
            zone_results = zone_cur.fetchall()
            all_price_filled = True
            # check if the user has input the price of all zones.
            for zone in zone_results:
                if request.form[f'priceFor-{zone["id"]}'] == '':
                    all_price_filled = False
                    flash('Please enter price for row {} to row {}'.format(zone['startRow'],
                                                                           zone['endRow']), 'error')
                    break
            if all_price_filled: 
                # insert event into database.               
                start_dt = datetime.strptime(request.form['start_datetime'], "%Y-%m-%dT%H:%M")
                start_dt = datetime.strftime(start_dt, "%Y-%m-%d %H:%M")
                start_date, start_time = start_dt.split(' ')
                end_dt = datetime.strptime(request.form['end_datetime'], "%Y-%m-%dT%H:%M")
                end_dt = datetime.strftime(end_dt, "%Y-%m-%d %H:%M")
                end_date, end_time = end_dt.split(' ')
                poster = request.files.get('poster', '').read()
                db.execute('''insert into events (title, startDate, startTime, endDate, endTime, 
                                                location, hostedBy, poster, layoutId, status)
                        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''' ,\
                    [                
                        request.form['title'],
                        start_date,
                        start_time,
                        end_date,
                        end_time,
                        request.form['location'],
                        user['id'],
                        poster,
                        layout_choice,
                        'v'
                    ]
                )
                db.commit()    
                # Insert prices for different zones for this event   
                current_event_cur = db.execute('''select * from Events order by id desc limit 1;''')
                current_event_result = current_event_cur.fetchall()
                for zone in zone_results:
                    zone_price = request.form[f'priceFor-{zone["id"]}']
                    db.execute('''insert into Price (forEvent, forZone, price, status)
                               values (?, ?, ?, ?)''', [current_event_result[0][0], zone['id'], zone_price, 'v'])
                    db.commit()               

    # extract all events created by this user
    events_cur = db.execute('''
            select e.*, u.name as host, min(p.price) as min_price
            from Events e, Users u, Price p
            where e.hostedBy = u.id and u.id = ? and p.forEvent = e.id and p.status = "v" 
            group by e.id
            order by e.startDate''', [user['id']])

    events_results = events_cur.fetchall()

    layout_cur = db.execute('''select id, row, column from Layouts''')
    layout_results = layout_cur.fetchall()

    zone_cur = db.execute('''select id, startRow, endRow, layoutId from Zones''')
    zone_results = zone_cur.fetchall()

    base64_imgs = dict()
    for e in events_results:
        base64_imgs[e['id']] = base64.b64encode(e['poster']).decode('utf-8')
        
    return render_template('addevents.html', user=user, events=events_results, 
                           imgs = base64_imgs, layouts=layout_results, zones=zone_results)

@app.route('/tickets', methods=['GET'])
def tickets():
    ''' function to handle the tickets page of registered customers'''
    user = get_current_user()
    db = get_db()
    
    # get all tickets sold to this customer
    sold_tickets_cur = db.execute('''select id, soldTo, forEvent, row, column,
                                  transactionId, soldPrice, status
                                  from SoldTickets
                                  where soldTo={}'''.format(user['id']))
    sold_tickets = sold_tickets_cur.fetchall()

    # convert each "ROW" object into the "dict" object
    # so that we can convert it into json in the js function
    # otherwise only string would be passed to the function
    sold_tickets_dict = [dict(row) for row in sold_tickets]
    length = len(sold_tickets)
    
    # extract the corresponding events and transaction records of all tickets sold to this customer
    events = []
    transactions = []
    for i in range(length):
        events_cur = db.execute('''select id, title, startDate, startTime, endDate, endTime,
                                location, hostedBy, status
                                from Events
                                where id={}'''.format(sold_tickets[i]['forEvent']))
        event = events_cur.fetchone()
        events.append(dict(event))
        
        transaction_cur = db.execute('''select id, boughtBy, transactionDate
                                     from Transactions
                                     where id={}'''.format(sold_tickets[i]['transactionId']))
        transcation = transaction_cur.fetchone()
        transactions.append(dict(transcation))
        
    return render_template('tickets.html', user=user, soldTickets=sold_tickets_dict, events=events, transactions=transactions, length=length)

@app.route('/cancelTicket/<fromPage>/<id>/<eventTitle>', methods=['POST'])
def cancelTicket(fromPage, id, eventTitle):
    '''function for ticket cancellation'''
    db = get_db()

    # check if the ticket have been cancelled already
    check_ticket_cur = db.execute('''select st.id from SoldTickets st where st.id = ? and st.status = 'v' ''', [id])
    check_ticket = check_ticket_cur.fetchall()
    if not check_ticket:
        flash('The ticket has been cancelled already', 'error')
        return redirect(url_for(fromPage)) 
    # update the sold record to 'c'
    db.execute('''update SoldTickets set status = ? where 
                  id = ?''', ['c', id])
    db.commit()
        
    user = get_current_user()

    if request.method == 'POST':        
        email_recipients = [user['email']]
        
        # only send email if there are recipients
        if email_recipients:
            email_title = "EventBooker: Ticket Cancellation!"
            email_message = f"""
            Dear \"{user['name']}\", <br>
            <br>
            The ticket for event \"{eventTitle}\" has been cancelled by you. <br>
            The ticket you have booked will be refunded to your payment card. <br>
            <br>
            
            Best,<br>
            Event Management System 
            """
            send_email(senderName, email_title, email_message, bcc=email_recipients)
                
    return redirect(url_for(fromPage)) 

@app.route('/wishlist', methods=['GET', 'POST'])
def wishlist():
    '''function for wishlist page'''
    user = get_current_user()
    db = get_db()
    # extract all wishlist events associated with this user
    event_cur =db.execute('''select e.*, w.*, u.name as host, min(p.price) as min_price from Events e, Wishlist w, Users u, Price p
                             where w.userId = ? and w.eventId =e.id and e.hostedBy = u.id and p.forEvent = e.id and p.status = "v" 
                             group by e.id''',[user['id']])

    event_result = event_cur.fetchall()
    base64_imgs = []
    for e in event_result:
        base64_imgs.append(base64.b64encode(e['poster']).decode('utf-8'))
        
    if user == None:
        wishlist_result = None
    else:
        # construct the wishlist event list for cross checking
        wishlist_result=[]
        for e in event_result:
            wishlist_cur = db.execute('select w.* from Wishlist w where userId = ? and eventId = ?',[user['id'],e['id']])
            wishlist_res = wishlist_cur.fetchone()
            wishlist_result.append(wishlist_res)
    
    # handle adding and removing wishlist
    if request.method == 'POST' and "addwishlist" in request.form:
        db.execute('insert into Wishlist(userId, eventId) values(?,?)',[user['id'],int(request.form['addwishlist'])]) 
        db.commit()
        return redirect(url_for('wishlist'))  
    if request.method == 'POST' and 'removewishlist' in request.form:
        db.execute('delete from Wishlist where userId=? and eventId =?',[user['id'],int(request.form['removewishlist'])])
        db.commit()
        return redirect(url_for('wishlist'))        

    return render_template('wishlist.html', user=user, events=event_result, imgs = base64_imgs, wishlist=wishlist_result)

@app.route('/event/<id>', methods=['GET', 'POST'])
def event(id):
    '''function for event.html'''
    user = get_current_user()
    db = get_db()
    
    event_cur = db.execute('SELECT e.*,  e.startDate || e.startTime as startDatetime, datetime("now") as curDatetime FROM Events e WHERE id = ?',[id])
    event_result = event_cur.fetchone()
    base64_img = base64.b64encode(event_result['poster']).decode('utf-8')

    host_cur = db.execute('SELECT u.* FROM Users u WHERE id = ?', [event_result['hostedBy']])
    host_result = host_cur.fetchone()

    layout_cur = db.execute('SELECT l.* FROM Layouts l WHERE id = ?', [event_result['layoutId']])
    layout_result = layout_cur.fetchone()
    seats_result = []

    sold_cur = db.execute('SELECT s.* FROM SoldTickets s WHERE forEvent = ?', [id])
    sold_result = sold_cur.fetchall()

    for row in range(layout_result['row']):
        seats_result.append([])
        for col in range(layout_result['column']):
            seats_result[row].append(False)

    # check if the seat has been sold
    for sold in sold_result:
        if (sold['status'] != 'c'):
            seats_result[sold['row']-1][sold['column']-1] = True

    # extract the price of each zones
    zones_cur = db.execute('SELECT z.* FROM Zones z WHERE layoutId = ?', [event_result['layoutId']])
    zones_result = zones_cur.fetchall()
    prices_cur = db.execute('SELECT p.* FROM Price p WHERE status = "v" and forEvent = ?', [id])
    prices_result = prices_cur.fetchall()
    prices = []

    for row in range(layout_result['row']):
        prices.append([])
        cur_zone = None
        for z in zones_result:
            if row+1 >= z['startRow'] and row+1 <= z['endRow']:
                cur_zone = z['id']
                break
        for col in range(layout_result['column']):
            cur_price = None
            for p in prices_result:
                if p['forZone'] == cur_zone:
                    cur_price = p
                    break
            if cur_price:
                prices[row].append(cur_price['price'])
            else:
                prices[row].append(0)
    
    # handling comments (i.e. comments with replies, comment solo)
    comments_with_replies_cur = db.execute('''SELECT Comments.comment, Comments.id, Comments.commentTime, Users.name, Replies.reply, Replies.replyTime
    FROM Comments JOIN Users, Replies  
    WHERE Users.id  = Comments.userId and Comments.id = Replies.commentId and Comments.eventId = ?''', [id])
    comments_with_replies_result = comments_with_replies_cur.fetchall()
    comments_solo_cur = db.execute('''SELECT Comments.comment, Comments.id, Comments.commentTime, Users.name 
            FROM Comments JOIN Users  
            WHERE Users.id  = Comments.userId and 
            Comments.id NOT in 
            (SELECT Comments.id FROM Comments JOIN  Replies  WHERE Comments.id = Replies.commentId and Comments.eventId = ?) 
            and Comments.eventId = ?''', [id, id])
    comments_solo_result = comments_solo_cur.fetchall()

    if request.method == 'POST':
        # check if the post form is the buying tickets form or the comment form
        search_type_seats = request.form.get('selected_seats', None)
        search_type_reply = request.form.get('reply', None)
        search_type_comment = request.form.get('comment', None)
        # for posting replies
        if search_type_reply:
            if request.form['reply'].strip() == "":
                return redirect(url_for('event', id =id), code=303) 
            else:
                datenow = datetime.now().strftime("%Y-%m-%d, %H:%M:%S")
                db.execute('''INSERT into Replies (reply, replyTime, commentId, hostId) values (?, ?, ?, ?)''', [request.form['reply'], datenow, request.form['commentID'], user['id']])
                db.commit()

            comments_with_replies_cur = db.execute('''SELECT Comments.comment, Comments.id, Comments.commentTime, Users.name, Replies.reply, Replies.replyTime, Users.email
            FROM Comments JOIN Users, Replies  
            WHERE Users.id  = Comments.userId and Comments.id = Replies.commentId and Comments.eventId = ?''', [id])
            comments_with_replies_result = comments_with_replies_cur.fetchall()
            comments_solo_cur = db.execute('''SELECT Comments.comment, Comments.id, Comments.commentTime, Users.name 
            FROM Comments JOIN Users  
            WHERE Users.id  = Comments.userId and 
            Comments.id NOT in 
            (SELECT Comments.id FROM Comments JOIN  Replies  WHERE Comments.id = Replies.commentId and Comments.eventId = ?) 
            and Comments.eventId = ?''', [id, id])
            comments_solo_result = comments_solo_cur.fetchall()

            # send email to customer when host replies comment.
            customer_cur = db.execute(''' select u.name, u.email from Users u, Comments c where u.id=c.userId and c.id = ? ''', [request.form['commentID']])
            customer_result = customer_cur.fetchone()

            email_recipients_list = []
            email_recipients_list.append(customer_result['email'])

            email_title = "EventBooker: The Host has replied your comment!"
            email_message = f"""
            Dear customer, <br>
            <br>
            The host for event \"{event_result['title']}\" has replied your comment. <br>
            Please check it out. <br>
            <br>
            
            Best,<br>
            Event Management System 
            """
            send_email(senderName, email_title, email_message, recipients=email_recipients_list)
            return redirect(url_for('event', id=id), code = 303)
            #return render_template('event.html', event=event_result, poster=base64_img, host=host_result, seats=seats_result, layout=layout_result, prices=prices, comments=comments_solo_result, com_rep = comments_with_replies_result)
        # for postinig comment
        elif search_type_comment:
            if request.form['comment'].strip() == "":
                return redirect(url_for('event', id =id), code=303) 
            else:
                datenow = datetime.now().strftime("%Y-%m-%d, %H:%M:%S")
                db.execute('''INSERT into Comments (comment, commentTime, userId, eventId) values (?, ?, ?, ?)''', [request.form['comment'], datenow, user['id'], id])
                db.commit()

            comments_with_replies_cur = db.execute('''SELECT Comments.comment, Comments.id, Comments.commentTime, Users.name, Replies.reply, Replies.replyTime
            FROM Comments JOIN Users, Replies  
            WHERE Users.id  = Comments.userId and Comments.id = Replies.commentId and Comments.eventId = ?''', [id])
            comments_with_replies_result = comments_with_replies_cur.fetchall()
            comments_solo_cur = db.execute('''SELECT Comments.comment, Comments.id, Comments.commentTime, Users.name 
            FROM Comments JOIN Users  
            WHERE Users.id  = Comments.userId and 
            Comments.id NOT in 
            (SELECT Comments.id FROM Comments JOIN  Replies  WHERE Comments.id = Replies.commentId and Comments.eventId = ?) 
            and Comments.eventId = ?''', [id, id])
            comments_solo_result = comments_solo_cur.fetchall()
            return redirect(url_for('event', id =id),code=303) 
            #return render_template('event.html', event=event_result, poster=base64_img, host=host_result, seats=seats_result, layout=layout_result, prices=prices, comments=comments_solo_result, com_rep = comments_with_replies_result)
        #for buying tickets
        elif search_type_seats:
            temp = request.form['selected_seats'].split()
            total = request.form['total']
            sold_tickets = []
            for t in temp:
                sold = {}
                temp_cl = re.split('c|r', t)
                sold['row'] = int(temp_cl[1])
                sold['column'] = int(temp_cl[2])
                sold_tickets.append(sold)

            # check if the event has been cancelled by the host
            if event_result['status'] == 'c':
                flash('The event has been cancelled by the host', 'error')
                return redirect(url_for('event', id=id), code =303)

            # check if the tickets have been sold
            for st in sold_tickets:
                check_ticket_cur = db.execute('''select st.id from SoldTickets st where st.status = 'v' and st.forEvent = ? and row = ? and column = ? ''', [id, st['row'], st['column']])
                check_ticket = check_ticket_cur.fetchall()
                if check_ticket:
                    flash('Tickets already been sold. Please select other tickets', 'error')
                    return redirect(url_for('event', id=id), code =303)

            # transactionDate format is: YYYY-MM-DD 
            datenow = datetime.now().strftime("%Y-%m-%d")

            db.execute('''INSERT into Transactions (boughtBy, transactionDate) values (?, ?)''', [user['id'], datenow])
            db.commit()

            trans_cur = db.execute('''SELECT t.* FROM Transactions t WHERE boughtBy = ? and transactionDate = ? ORDER BY id DESC''', [user['id'],datenow])
            trans_result = trans_cur.fetchone()

            for st in sold_tickets:
                db.execute('''INSERT into SoldTickets (soldTo, forEvent, row, column, transactionId, soldPrice, status) values (?, ?, ?, ?, ?, ?, ?)''',[
                    user['id'],
                    id,
                    st['row'],
                    st['column'],
                    trans_result['id'],
                    prices[st['row']-1][st['column']-1],
                    'v'])
                db.commit()
            
            # send email to customer
            email_recipients_list = [user['email']]

            email_title = "EventBooker: Event Tickets Purchase Conformation!"
            email_message = f"""
            Dear Customer, <br>
            <br>
            Thanks for booking through our system. <br>
            Below please find the Purchase details.<br>
            Transaction Id: {trans_result['id']} <br>
            """

            for st in sold_tickets:
                email_message += f"Row: {st['row']}, Column: {st['column']}<br>"
            
            email_message += f"""
            <br>
            Total cost: ${total}<br>
            <br>        
            Best,<br>
            Event Management System 
            """
            send_email(senderName, email_title, email_message, recipients=email_recipients_list)

            return redirect(url_for('event', id=id), code =303)
    return render_template('event.html', event=event_result, poster=base64_img, host=host_result, seats=seats_result, layout=layout_result, prices=prices, comments=comments_solo_result, com_rep = comments_with_replies_result)

@app.route('/eventedit/<event_id>', methods=['GET'])
def event_edit(event_id):
    '''function for event editing'''
    db = get_db()
    event_data_cur = db.execute('SELECT * FROM Events WHERE id = ?', [event_id])
    event_data = event_data_cur.fetchone()

    rawPoster = event_data['poster']
    poster64=base64.b64encode(rawPoster).decode('utf-8')
    # add for fire sales function
    event_prices_cur = db.execute('''select p.*, pp.price as oldPrice, z.startRow, z.endRow
    from price p 
        LEFT JOIN price pp on p.origPriceId = pp.id ,
    zones z
    where p.status = 'v' and p.forZone = z.id and p.forEvent = ?
    order by z.startRow''', [event_id])
    event_prices = event_prices_cur.fetchall()
    # get the layout and sales information
    layout_cur = db.execute('''select l.id, l.row, l.column from Layouts l, Events e where e.layoutId = l.id and e.id = ?''', [event_id])
    layout_results = layout_cur.fetchone()

    seats_result = []

    sold_cur = db.execute('SELECT s.* FROM SoldTickets s WHERE forEvent = ?', [event_id])
    sold_result = sold_cur.fetchall()

    for row in range(layout_results['row']):
        seats_result.append([])
        for col in range(layout_results['column']):
            seats_result[row].append(False)

    # Check if the seats have been sold
    for sold in sold_result:
        if (sold['status'] != 'c'):
            seats_result[sold['row']-1][sold['column']-1] = True

    zone_cur = db.execute('''select id, startRow, endRow, layoutId from Zones''')
    zone_results = zone_cur.fetchall()

    return render_template('eventedit.html', event_id=event_id, event_data=event_data, poster64=poster64, event_prices=event_prices, layouts=layout_results, zones=zone_results, seats=seats_result)

@app.route('/firesales/<event_id>/', methods=['GET','POST'])
def firesales(event_id):
    '''function for fire sale'''
    db = get_db()
    if request.method == 'POST':   
        price_changed = False
        # extract the prices of the event
        event_prices_cur = db.execute('''select p.*, pp.price as oldPrice, z.startRow, z.endRow
            from price p 
                LEFT JOIN price pp on p.origPriceId = pp.id ,
            zones z
            where p.status = 'v' and p.forZone = z.id and p.forEvent = ?
            order by z.startRow''', [event_id])
        event_prices = event_prices_cur.fetchall()
        new_price_update_list = []
        old_price_update_list = []
        price_message = []
        for price in event_prices:
            # extract the original price for the price that is already on sale
            oldPrice = price['price'] if price['origPriceId'] == -1 else price['oldPrice']
            curPrice = price['price']
            newPrice = request.form[f"priceFor-{price['forZone']}"]
            price_message.append(f"Row {price['startRow']} to row {price['endRow']}: {newPrice} <br>")
            # handle empty input
            if newPrice == '':
                price_changed = False
                flash('Fire Sales Warning: Please enter the new price for row {} to row {}!'.format(price['startRow'],
                                                                        price['endRow']), 'error')
                return redirect(url_for('event_edit', event_id =event_id), code=303) 
            # handle 0 price
            if int(float(newPrice)*100) == 0:
                price_changed = False
                flash('Fire Sales Warning: New price cannot be $0. Please check the new price for row {} to row {}!'.format(price['startRow'],
                                                                        price['endRow']), 'error')
                return redirect(url_for('event_edit', event_id =event_id), code=303) 
            # new price cannot be greater than the current price
            if int(float(newPrice)*100) > int(curPrice*100):
                flash('Fire Sales Warning: New price cannot be greater than the current price. Please check the new price for row {} to row {}!'.format(price['startRow'],
                                                                        price['endRow']), 'error')
                return redirect(url_for('event_edit', event_id =event_id), code=303) 
            # if the new price is different from the original price
            if int(float(newPrice)*100) != int(oldPrice*100):
                # handle prices that are not on sale yet
                if price['origPriceId'] == -1:
                    origPriceId = price['id']
                    new_price_update_list.append((event_id, price['forZone'], newPrice, 'v', 1, origPriceId))
                    old_price_update_list.append((origPriceId,))
                # handle prices that are already on sale
                else:
                    origPriceId = price['origPriceId']
                    new_price_update_list.append((event_id, price['forZone'], newPrice, 'v', 1, origPriceId))
                    old_price_update_list.append((price['id'],))
                price_changed = True
        # update price table
        if price_changed:
            if new_price_update_list:
                db.executemany('''INSERT INTO Price
                            (forEvent, forZone, price, status, fireSales, origPriceId)
                            VALUES (?, ?, ?, ?, ?, ?) ''', new_price_update_list)
                db.commit()
            if old_price_update_list:
                db.executemany('''Update Price set status = 'c' where id = ? ''', old_price_update_list)
                db.commit()
            # send emails to wishlist excluding ticket holders
            email_recipients_list=group_email_address(event_id, 2)
            if email_recipients_list:
                event_cur = db.execute('select * from Events e where e.id = ? ', [event_id])
                event_data = event_cur.fetchone();
                email_title = "EventBooker: Fire Sales! - The event in your wishlist is on sale!"
                email_message = f"""
                Dear Customer, <br>
                <br>
                The price of the event \"{event_data['title']}\" has been updated by the host. <br>
                Below please find the updated price: <br>"""
                for m in price_message:
                    email_message += m
                email_message += """
                Thanks for your attention！ <br>
                <br>

                Best,<br>
                Event Management System 
                """
                send_email(senderName, email_title, email_message, bcc=email_recipients_list)

    return redirect(url_for('event_edit', event_id =event_id), code=303) 

@app.route('/event_update/<event_id>', methods=['GET','POST'])
def event_update(event_id):
    '''function for event updating process'''
    user = get_current_user()
    db = get_db()
    event_data = db.execute('SELECT * FROM Events WHERE id = ?', [event_id]).fetchone()
    poster64=base64.b64encode(event_data['poster']).decode('utf-8')
    
    if request.method == 'POST':
        # check if all inputs are valid
        current_datetime = datetime.now()
        if request.form['title'] == "":            
            flash('Please enter the event title','error')
        elif request.form['start_datetime'] == "":
            flash('Please choose a start Date&Time','error')
        elif request.form['end_datetime'] == "":
            flash('Please choose an end Date&Time','error')
        elif request.form['end_datetime'].split('-')[0] < request.form['start_datetime'].split('-')[0]:
            flash('The end date year cannot be earlier than the start date year!','error')
        elif request.form['end_datetime'].split('-')[1] < request.form['start_datetime'].split('-')[1]:
            flash('The end date month cannot be earlier than the start date month!','error')
        elif request.form['end_datetime'].split('-')[2] < request.form['start_datetime'].split('-')[2]:
            flash('The end date day cannot be earlier than the start date day!','error')
        elif (request.form['end_datetime'].split('T')[0] == request.form['start_datetime'].split('T')[0] 
            and request.form['end_datetime'].split('T')[1].split(':')[0] < request.form['start_datetime'].split('T')[1].split(':')[0]):
            flash('The end date hour cannot be earlier than the start hour year!','error')
        elif (request.form['end_datetime'].split('T')[0] == request.form['start_datetime'].split('T')[0] 
            and request.form['end_datetime'].split('T')[1].split(':')[0] == request.form['start_datetime'].split('T')[1].split(':')[0]
            and request.form['end_datetime'].split('T')[1].split(':')[1] < request.form['start_datetime'].split('T')[1].split(':')[1]):
            flash('The end date minute cannot be earlier than the start date minute!','error')  
        elif request.form['start_datetime'].replace('T', ' ') <= str(current_datetime):
            flash('The start datetime cannot be earlier than current datetime!','error')  
        elif request.form['location'] == "":
            flash('Please choose a location','error')  
        elif (request.form['title'] == event_data['title']
            and request.form['location'] == event_data['location']
            and request.form['start_datetime'] == f"{event_data['startDate']}T{event_data['startTime']}"
            and request.form['end_datetime'] == f"{event_data['endDate']}T{event_data['endTime']}"):
            if str(request.files.get('poster'))=="<FileStorage: '' ('application/octet-stream')>":
                flash(f"Nothing has been updated.",'error')
            else:
                poster = request.files.get('poster', '').read()
                db.execute('''
                    UPDATE events
                    SET poster = ?
                    WHERE id = ?
                ''', (
                    poster,
                    event_id
                ))
                db.commit()
        else:
            # update the event details in database
            start_dt = datetime.strptime(request.form['start_datetime'], "%Y-%m-%dT%H:%M")
            start_dt = datetime.strftime(start_dt, "%Y-%m-%d %H:%M")
            start_date, start_time = start_dt.split(' ')
            end_dt = datetime.strptime(request.form['end_datetime'], "%Y-%m-%dT%H:%M")
            end_dt = datetime.strftime(end_dt, "%Y-%m-%d %H:%M")
            end_date, end_time = end_dt.split(' ')
            if str(request.files.get('poster'))=="<FileStorage: '' ('application/octet-stream')>":
                db.execute('''
                    UPDATE events
                    SET title = ?,
                        startDate = ?,
                        startTime = ?,
                        endDate = ?,
                        endTime = ?,
                        location = ?
                    WHERE id = ?
                ''', (
                    request.form['title'],
                    start_date,
                    start_time,
                    end_date,
                    end_time,
                    request.form['location'],
                    event_id
                ))
                db.commit()
            else:
                poster = request.files.get('poster', '').read()
                db.execute('''
                    UPDATE events
                    SET title = ?,
                        startDate = ?,
                        startTime = ?,
                        endDate = ?,
                        endTime = ?,
                        location = ?,
                        poster = ?
                    WHERE id = ?
                ''', (
                    request.form['title'],
                    start_date,
                    start_time,
                    end_date,
                    end_time,
                    request.form['location'],
                    poster,
                    event_id
                ))
                db.commit()
            
            # send emails to wishlist customers and ticket holders.
            group1=group_email_address(event_id, 1)
            group2=group_email_address(event_id, 0)
            email_recipients_list=list(set(group1+group2))
            if email_recipients_list:
                email_title = "EventBooker: The event related to you has NEW UPDATE!"
                email_message = f"""
                Dear Customer, <br>
                <br>
                The event \"{event_data['title']}\" has been updated by the host. <br>
                There are the new details: <br>
                The Event Tilte: \"{request.form['title']}\" . <br>
                The StartDate: \"{start_date}\" . <br>
                The StartTime: \"{start_time}\" . <br>
                The EndDate \"{end_date}\" . <br>
                The EndTime \"{end_time}\" . <br>
                The Location \"{request.form['location']}\" . <br>
                Thanks for your attention！ <br>
                <br>

                Best,<br>
                Event Management System 
                """
                send_email(senderName, email_title, email_message, bcc=email_recipients_list)

    return redirect(url_for('event_edit', event_id =event_id))   

@app.route('/cancelEvent/<fromPage>/<id>', methods=['POST'])
def cancelEvent(fromPage, id):
    '''function for event cancellation process'''
    db = get_db()
    event_cur = db.execute('select e.* from Events e where id = ?',[id])
    event_result = event_cur.fetchone()
    user = get_current_user()

    if request.method == 'POST':
        # set event to 'cancel'
        db.execute('update Events set status = ? where id = ?', ['c' ,id])
        db.commit()
        
        # send email to ticket holders
        email_recipients_list=group_email_address(id, 1)
        if email_recipients_list:
            email_title = "EventBooker: Event Cancellation!"
            email_message = f"""
            Dear Customer, <br>
            <br>
            The event \"{event_result['title']}\" has been cancelled by the host. <br>
            The ticket(s) you have booked will be refunded to your payment card. <br>
            <br>
            
            Best,<br>
            Event Management System 
            """

            for email in email_recipients_list:
                send_email(senderName, email_title, email_message, recipients=[email])

            # set all related tickets to 'cancel'
            db.execute('update SoldTickets set status = ? where forEvent = ?', ['c',id])
            db.commit()

        # send email to wishlist customer
        email_recipients_list=group_email_address(id, 0)
        if email_recipients_list:
            email_title = "EventBooker: Your wishlist events have NEW UPDATE!"
            email_message = f"""
            Dear Customer, <br>
            <br>
            The event \"{event_result['title']}\" has been cancelled by the host. <br>
            Thanks for your attention！ <br>
            <br>
            
            Best,<br>
            Event Management System 
            """
            send_email(senderName, email_title, email_message, bcc=email_recipients_list)
        
    return redirect(url_for(fromPage), code=303) 

@app.route('/logout')
def logout():
    session.pop('emailaddress', None)
    session.pop('is_host', None)

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
