// Trockenlauf des Jenkinsfile ohne Jenkins: deklarative DSL als Stubs, alle sshCommand-Befehle werden mit den
// Parametern gerendert und mit `bash -n` geprüft. Aufruf: groovy deploy/jenkinsfile-pruefen.groovy Jenkinsfile [test|prod]
// Die gerenderten Befehle landen in build/jenkins-befehle-<env>.sh (zum Nachlesen).
class Env { Map m = [:]; def propertyMissing(String n) { m[n] }; def propertyMissing(String n, v) { m[n] = v?.toString() } }
def envObj = new Env()
def params = [TARGET_SERVER: 'dpn-svr-iot', ENVIRONMENT: args.length > 1 ? args[1] : 'test', IMAGE_TAG_BACKEND: 'abc123',
              IMAGE_TAG_FRONTEND: 'abc123', RELOAD_EXPORTS: 'yes', PUBLIC_BASE_URL: 'https://iot.polipol-service.de',
              DNS_RESOLVER: '127.0.0.11']
def befehle = []
def script = new GroovyShell(new Binding([params: params, env: envObj])).parse(new File(args[0]).text)
def mc = script.metaClass
def ev = { c -> if (c) { c.delegate = script; c.resolveStrategy = Closure.DELEGATE_FIRST; c() } }
['pipeline', 'stages', 'steps', 'script', 'options', 'post', 'failure', 'aborted', 'success', 'parameters'].each { n ->
    mc."$n" = { Closure c -> ev(c) }
}
mc.agent = { a -> }
mc.any = null
mc.choice = { Map m -> }
mc.string = { Map m -> }
mc.timestamps = { -> }
mc.disableConcurrentBuilds = { -> }
mc.timeout = { Map m -> }
mc.environment = { Closure c ->
    // Zuweisungen im environment-Block landen in env; Werte dürfen frühere env-Werte und params referenzieren
    def d = new Object() {
        def propertyMissing(String n, v) { envObj.m[n] = v.toString() }
        def propertyMissing(String n) { envObj.m.containsKey(n) ? envObj.m[n] : params[n] }
    }
    c.delegate = d
    c.resolveStrategy = Closure.DELEGATE_FIRST
    c()
}
mc.stage = { String n, Closure c -> println "== Stage $n"; ev(c) }
mc.when = { Closure c -> }
mc.expression = { Closure c -> }
mc.echo = { s -> println "   echo: $s" }
mc.error = { s -> throw new RuntimeException("error(): $s") }
mc.sleep = { n -> }
mc.catchError = { Map m, Closure c -> c() }
mc.withCredentials = { List l, Closure c ->
    script.binding.setVariable('REMOTE_USR', 'u')
    script.binding.setVariable('REMOTE_PSW', 'p')
    c()
}
mc.usernamePassword = { Map m -> m }
mc.sshCommand = { Map m -> befehle << m.command; m.command.contains('Health.Status') ? 'healthy' : '' }
// env-Variablen auch direkt als Namen auflösbar (wie in Jenkins)
mc.propertyMissing = { String n -> if (envObj.m.containsKey(n)) return envObj.m[n]; throw new MissingPropertyException(n) }
script.run()

println "\n${befehle.size()} Shell-Befehle"
new File('build').mkdirs()
new File("build/jenkins-befehle-${params.ENVIRONMENT}.sh").text =
    befehle.withIndex().collect { b, i -> "# --- Befehl ${i + 1}\n$b\n" }.join('\n')
def fehler = 0
befehle.eachWithIndex { b, i ->
    def f = File.createTempFile('cmd', '.sh')
    f.text = b
    def p = ['bash', '-n', f.path].execute()
    p.waitFor()
    if (p.exitValue() != 0) { fehler++; println "SYNTAXFEHLER in Befehl ${i + 1}: ${p.err.text}" }
}
println fehler ? "$fehler Befehl(e) fehlerhaft" : 'bash -n: alle Befehle in Ordnung'
System.exit(fehler ? 1 : 0)
