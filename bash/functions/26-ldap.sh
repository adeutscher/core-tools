
# Basic LDAP functions/aliases.


if ! __is_unix && qtype ldapsearch.exe; then
    # Tab-completion in MobaXterm hops to ldapsearch.exe.
    # Not that there's any performance difference,
    #    but for comfort making aliases that will complete to ldapsearch
    
    # Assuming for the moment that the commands are otherwise identical
    
    alias ldapcompare='ldapcompare.exe'
    alias ldapdelete='ldapdelete.exe'
    alias ldapmodify='ldapmodify.exe'
    alias ldapmodrdn='ldapmodrdn.exe'
    alias ldappasswd='ldappasswd.exe'
    alias ldapsearch='ldapsearch.exe'
    alias ldapwhoami='ldapwhoami.exe'
    alias ldapurl='ldapurl.exe'
fi
