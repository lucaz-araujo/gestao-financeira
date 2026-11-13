import { useEffect,useState } from 'react';
import { Alert,Button,Form,Input,Typography } from 'antd';
import { Link,useLocation,useNavigate } from 'react-router-dom';
import { ApiError,errorMessage,publicUserPost } from '../api';
import { useSession } from '../session';
import { Brand } from '../components/Brand';
export function PasswordRecovery(){
 const {clearSession}=useSession();
 const location=useLocation(),navigate=useNavigate();
 const [token,setToken]=useState(()=>new URLSearchParams(window.location.hash.slice(1)).get('token'));
 const [error,setError]=useState(''),[done,setDone]=useState(false),[loading,setLoading]=useState(false);
 useEffect(()=>{const next=new URLSearchParams(location.hash.slice(1)).get('token');if(next){setToken(next);setDone(false);setError('');navigate(location.pathname+location.search,{replace:true});}},[location.hash,location.pathname,location.search,navigate]);
 async function submit(values:Record<string,string>){setLoading(true);setError('');try{await publicUserPost('/usuario/api/recuperacao/'+(token?'confirmar/':'solicitar/'),{...values,...(token?{token}:{})});setDone(true);if(token)clearSession();}catch(e){setError(e instanceof ApiError&&e.status===503?e.message:errorMessage(e));}finally{setLoading(false);}}
 return <div className="login-shell"><section className="login-story"><div className="brand"><Brand/></div><div><div className="eyebrow">SEGURANÇA DA CONTA</div><h1>Recupere<br/>seu <em>acesso.</em></h1><p>Use um link de recuperação para definir uma nova senha.</p></div></section><main className="login-card"><Typography.Title level={2}>{token?'Definir nova senha':'Recuperar acesso'}</Typography.Title>{error&&<Alert type="error" title={error} showIcon style={{marginBottom:20}}/>}{done?<Alert type="success" showIcon title={token?'Senha alterada. Entre novamente.':'Se os dados corresponderem a uma conta ativa, você receberá as instruções por e-mail.'}/>:<Form layout="vertical" onFinish={submit} requiredMark={false}>{token?<><p>Use pelo menos 12 caracteres.</p><Form.Item name="new_password" label="Nova senha" rules={[{required:true},{min:12,message:'Use pelo menos 12 caracteres.'}]}><Input.Password maxLength={256} autoComplete="new-password"/></Form.Item><Form.Item name="conf_password" label="Confirmar nova senha" dependencies={['new_password']} rules={[{required:true},({getFieldValue})=>({validator:async(_,value)=>{if(value!==getFieldValue('new_password'))throw new Error('As senhas não conferem.');}})]}><Input.Password maxLength={256} autoComplete="new-password"/></Form.Item></>:<><Form.Item name="username" label="Usuário" rules={[{required:true,message:'Informe o usuário.'}]}><Input maxLength={15} autoComplete="username"/></Form.Item><Form.Item name="email" label="E-mail" rules={[{required:true,message:'Informe o e-mail.'},{type:'email',message:'E-mail inválido.'}]}><Input maxLength={255} autoComplete="email"/></Form.Item></>}<Button type="primary" block htmlType="submit" loading={loading}>{token?'Salvar nova senha':'Enviar instruções'}</Button></Form>}<p style={{marginTop:24}}><Link to="/">Voltar para entrar</Link></p></main></div>;
}
export function SignOut(){
 const {signOut}=useSession(),navigate=useNavigate();const [error,setError]=useState(''),[loading,setLoading]=useState(false);
 async function exit(){setLoading(true);try{await signOut();navigate('/');}catch(e){setError(errorMessage(e));}finally{setLoading(false);}}
 return <div className="login-shell"><section className="login-story"><div className="brand"><Brand/></div><h1>Até<br/><em>breve.</em></h1></section><main className="login-card"><Typography.Title level={2}>Encerrar sessão</Typography.Title>{error&&<Alert type="error" title={error}/>}<p>Encerre o acesso neste navegador.</p><Button type="primary" onClick={exit} loading={loading}>Encerrar sessão</Button><p><Link to="/">Voltar</Link></p></main></div>;
}
