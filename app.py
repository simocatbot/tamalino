from flask import  Flask, request, render_template, jsonify, make_response, url_for, redirect, session, flash, send_from_directory
from pandas import DataFrame
import sqlite3, json, hashlib
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'S8x38%H*wW*lL1AY7p7QH8eSsx'
DATABASE = 'palmares.db'


def uploadToPalmares(players, scores, insertedBy):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO palmares (players, scores, insertedBy) VALUES(?,?,?)", (players, scores, insertedBy))
    conn.commit()
    cursor.close()
    conn.close()

def updateRankings(winner):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM players WHERE name = ?", [winner])
        row = cursor.fetchall()
        _id, _name, victories = row[0]
        victories +=1
        cursor.execute("UPDATE players SET victories= ? WHERE name = ?", (victories, winner))
        conn.commit()
        cursor.close()
        conn.close()
    except:
        #player not registered in the players database, need to register it first
        cursor.execute("INSERT INTO players (name, victories) VALUES(?,?)", (winner, 1))
        conn.commit()
        cursor.close()
        conn.close()

def getRankings():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT name, victories FROM players ORDER BY victories DESC")
    df = DataFrame(cursor.fetchall())
    df.columns=['Nome', 'Numero di Vittorie']
    df = df[df['Numero di Vittorie']>0]
    cursor.close()
    conn.close()
    return df


def getPalmares(startDate, endDate):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM palmares where timestamp >= ? AND timestamp <= ? ORDER BY timestamp ASC", (startDate,endDate))
    df = DataFrame(cursor.fetchall())
    if df.empty:
        flash("Mellon, non ci sono partite per le date selezionate, gioca più avidamente a Tamalo per riempire il PALMARES")
        return df
    else:
        df.columns = ['id', 'Data', 'Giocatori', 'Punteggi', 'Inserita da']
        df.drop('id',1, inplace=True)
        cursor.close()
        conn.close()
        df.Giocatori = df.Giocatori.str.replace('[','').str.replace(']','').str.replace("'",'')
        df.Punteggi = df.Punteggi.str.replace('[','').str.replace(']','')
        return df

def userIsRegistered(username):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        return True
    else:
        return False

def registerUser(username, hashedPassword):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (username, password) VALUES (?,?)", (username, hashedPassword))
    conn.commit()
    cursor.close()
    conn.close()

def loginUser(username):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT username, password FROM users WHERE username=?", (username,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:    
        username, hashedPassword = row
        return hashedPassword
    else: 
        return False

def logUserAccess(ipAddress, user):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO userAccesses (ipAddress, user) VALUES (?,?)", (ipAddress, user))
    conn.commit()
    cursor.close()
    conn.close()   


@app.route('/')
def landing():
    #session['logged'] = False
    if session.get('user') is None:
        user = 'Guest'
    else:
        user = session['user']
    ipAddress = request.remote_addr
    logUserAccess(ipAddress, user)
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    try:
        userLoggedOut = session['user']
        session.pop('logged', None)
        session.pop('user', None)
        flash( userLoggedOut + ' logged out!')
    except:
        flash('No user is logged!')
    return redirect(url_for('home'))

@app.route('/home')
def home():   
    #session['logged'] = False
    try:
        message = session['message']
    except:
        message=''   
    return render_template('home.html', message=message)


@app.route('/consulta', methods=['GET', 'POST'])
def consulta():
    #session['logged'] = False
    
    if request.method == 'POST':
        rankings = getRankings()

        startDate = request.form['startDate']
        endDate = request.form['endDate']
        matchesList = getPalmares(startDate, endDate)
        tables=[rankings.to_html(index=False, classes='data',header=True),  matchesList.to_html(index=False, classes='data', header=True)]
        render_template('consulta.html', tables=tables)

    else:

        rankings = getRankings()
        tables=[rankings.to_html(index=False, classes='data',header=True)]

    return render_template('consulta.html', tables=tables)

@app.route('/login', methods=['GET','POST'])
def login():
    #session['logged'] = False
    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']
        #check that both fields are filled
        if password and username:
            hashedPassword = hashlib.sha256(password.encode('utf-8')).hexdigest()
            pswFromDb = loginUser(username)
            if hashedPassword == pswFromDb:
                session['user']=username
                session['logged']=True
                ipAddress = request.remote_addr
                logUserAccess(ipAddress, session['user'])
                return redirect(url_for('home'))
            else:
                flash("Credenziali per accedere al Palmares ERRATE")
                return render_template('login.html')
        else:
            flash("Compila tutti i campi per entrare!")
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        #take username and password
        username = request.form['username']
        password = request.form['password']
        #check that both field are not empty
        if username and password:
            #check if user is already registered
            if userIsRegistered(username):
                flash('User già registrato')
                return render_template('register.html')
            else:
                hashedPassword = hashlib.sha256(password.encode('utf-8')).hexdigest()
                registerUser(username, hashedPassword)
                flash("User Registrato. " + username + " ,puoi ora effetuare il login!")
                return redirect(url_for('home'))          
        else:
            flash('Compila tutti i campi del form per la registrazione')
            return render_template('register.html')
    else:
        return render_template('register.html')

@app.route('/upload', methods=['GET', 'POST'])
def uploadResults():
    #session['logged']=True
    if not session.get('logged'):
        return  redirect(url_for('login'))

    if request.method == 'POST':

        formValues = request.values.to_dict()

        matchResult = []
        for value in formValues.values():
            matchResult.append(value)

        it = iter(matchResult)
        result = dict(zip(it,it))
        result = {x:int(y) for x,y in result.items() if x}
        sortedResults = {k: v for k, v in sorted(result.items(), key=lambda item: item[1])}
        
        players = list(sortedResults.keys())
        winner = players[0]
        players = str(players)
        scores = str(list(sortedResults.values()))
        
        insertedBy = session['user']
        uploadToPalmares(players, scores, insertedBy)
        updateRankings(winner)

        flash('Lunga vita al COMITATO! Mellon, grazie ancora una volta per aver giocato a TAMALO. La tua partita è stata aggiunta al Palmares.')

        return redirect(url_for('home'))#render_template('home.html', message=message)

    return render_template('upload.html')

@app.route('/regolamenti/<path:filename>')
def download_file(filename):
    return send_from_directory('regolamenti',filename, as_attachment=True)
